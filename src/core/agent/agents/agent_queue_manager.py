import queue
import time
import uuid
from collections.abc import Generator
from queue import Queue
from uuid import UUID

from redis import Redis

from src.core.agent.entities.queue_entity import AgentThought, QueueEvent
from src.entity.conversation_entity import InvokeFrom


class AgentQueueManager:
    """代理队列管理器，用于处理AgentThought事件的队列管理。

    该类提供了队列的基本操作功能，包括：
    - 监听队列消息（listen方法）
    - 发布事件到队列（publish方法）
    - 停止队列监听（stop_listen方法）
    - 错误处理（publish_error方法）
    - 任务状态检查（_is_stopped方法）

    同时集成了Redis缓存功能，用于：
    - 存储任务归属信息
    - 管理任务停止状态

    Attributes:
        q (Queue): 消息队列实例，用于存储AgentThought事件
        user_id (UUID): 用户ID，用于标识队列所属用户
        task_id (UUID): 任务ID，用于标识具体的任务
        invoke_from (InvokeFrom): 调用来源，可以是WEB_APP、DEBUGGER或其他来源
        redis_client (Redis): Redis客户端实例，用于缓存管理

    """

    user_id: UUID
    invoke_from: InvokeFrom
    redis_client: Redis
    _queues: dict[str, Queue]

    def __init__(
        self,
        user_id: UUID,
        invoke_from: InvokeFrom,
    ) -> None:
        """初始化Agent队列管理器

        Args:
            user_id (UUID): 用户ID，用于标识队列所属用户
            invoke_from (InvokeFrom): 调用来源，可以是WEB_APP、DEBUGGER或其他来源

        Attributes:
            user_id (UUID): 存储传入的用户ID
            invoke_from (InvokeFrom): 存储传入的调用来源
            _queues (dict): 存储队列实例的字典
            redis_client (Redis): 存储传入的Redis客户端实例

        """
        self.user_id = user_id
        self.invoke_from = invoke_from
        self._queues = {}

        from app.http.module import injector

        self.redis_client = injector.get(Redis)

    def listen(self, task_id: UUID) -> Generator:
        """监听队列消息的生成器函数

        Returns:
            Generator: 生成器，用于产生队列中的消息

        """
        # 设置监听超时时间为600秒（10分钟）
        listen_timeout = 600
        # 记录开始监听的时间戳
        start_time = time.time()
        # 记录上次发送PING事件的时间（以10秒为单位）
        last_ping_time = 0

        # 持续监听队列，直到遇到停止条件
        while True:
            try:
                # 从队列中获取消息，设置1秒超时
                item = self.queue(task_id).get(timeout=1)
                # 如果收到None，表示需要停止监听
                if item is None:
                    break
                # 产生队列中的消息
                yield item
            except queue.Empty:
                # 队列为空时继续循环
                continue
            finally:
                # 计算已经过的时间
                elapsed_time = time.time() - start_time

                # 每隔10秒发送一次PING事件，保持连接活跃
                if elapsed_time // 10 > last_ping_time:
                    self.publish(
                        task_id,
                        AgentThought(
                            id=uuid.uuid4(),
                            task_id=task_id,
                            event=QueueEvent.PING,
                        ),
                    )
                    # 更新上次发送PING的时间
                    last_ping_time = elapsed_time // 10

                # 检查是否超过监听超时时间
                if elapsed_time >= listen_timeout:
                    self.publish(
                        task_id,
                        AgentThought(
                            id=uuid.uuid4(),
                            task_id=task_id,
                            event=QueueEvent.TIMEOUT,
                        ),
                    )

                # 检查是否收到停止信号
                if self._is_stopped(task_id):
                    self.publish(
                        task_id,
                        AgentThought(
                            id=uuid.uuid4(),
                            task_id=task_id,
                            event=QueueEvent.STOP,
                        ),
                    )

    def stop_listen(self, task_id: UUID) -> None:
        """停止队列监听。

        通过向队列中放入None信号来停止监听。当listen方法从队列中获取到None时，会退出监听循环。

        Returns:
            None

        """
        self.queue(task_id).put(None)

    def publish(self, task_id: UUID, agent_queue_event: AgentThought) -> None:
        """发布代理队列事件。

        将事件放入队列中，并根据事件类型决定是否停止监听。如果事件类型为STOP、ERROR、TIMEOUT或AGENT_END，
        则会自动调用stop_listen方法停止监听。

        Args:
            task_id (UUID): 任务ID
            agent_queue_event (AgentThought): 要发布的代理队列事件对象

        Returns:
            None

        """
        self.queue(task_id).put(agent_queue_event)

        if agent_queue_event.event in [
            QueueEvent.STOP,
            QueueEvent.ERROR,
            QueueEvent.TIMEOUT,
            QueueEvent.AGENT_END,
        ]:
            self.stop_listen(task_id)

    def publish_error(self, task_id: UUID, error) -> None:
        """发布错误事件到队列。

        Args:
            task_id (UUID): 任务ID
            error: 错误对象，将被转换为字符串格式作为观察值

        Returns:
            None

        """
        self.publish(
            task_id,
            AgentThought(
                id=uuid.uuid4(),
                task_id=task_id,
                event=QueueEvent.ERROR,
                observation=str(error),
            ),
        )

    def _is_stopped(self, task_id: UUID) -> bool:
        """检查任务是否已停止

        通过检查Redis缓存中的任务停止标记来判断任务状态

        Returns:
            bool: 如果任务已停止返回True，否则返回False

        """
        # 生成任务停止状态的缓存键
        task_stopped_cache_key = self.generate_task_stopped_cache_key(task_id)
        # 从Redis获取任务停止标记
        result = self.redis_client.get(task_stopped_cache_key)

        # 如果缓存中存在停止标记则返回True，否则返回False
        return result is not None

    def queue(self, task_id: UUID) -> Queue:
        q = self._queues.get(str(task_id))

        if not q:
            # 根据调用来源确定用户前缀
            # WEB_APP和DEBUGGER使用"account"前缀
            # 其他来源使用"end-user"前缀
            user_prefix = (
                "account"
                if self.invoke_from in [InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER]
                else "end-user"
            )

            # 在Redis中设置任务归属缓存
            # 缓存键由task_id生成
            # 缓存过期时间为1800秒（30分钟）
            # 缓存值为用户前缀和用户ID的组合
            self.redis_client.setex(
                self.generate_task_belong_cache_key(task_id),
                1800,
                f"{user_prefix}-{self.user_id!s}",
            )

            q = Queue()
            self._queues[str(task_id)] = q

        return q

    @classmethod
    def generate_task_belong_cache_key(cls, task_id: UUID) -> str:
        """生成任务归属的缓存键。

        Args:
            task_id (UUID): 任务ID

        Returns:
            str: 格式化的任务归属缓存键，格式为 "generate_task_belong:{task_id}"

        """
        return f"generate_task_belong:{task_id!s}"

    @classmethod
    def generate_task_stopped_cache_key(cls, task_id: UUID) -> str:
        """生成任务停止状态的缓存键

        Args:
            task_id (UUID): 任务ID

        Returns:
            str: 格式化的缓存键字符串，用于在Redis中存储任务停止状态

        """
        return f"generate_task_stopped:{task_id!s}"

    @classmethod
    def set_stop_flag(
        cls,
        task_id: UUID,
        invoke_from: InvokeFrom,
        user_id: UUID,
    ) -> None:
        """设置任务停止标志。

        Args:
            task_id (UUID): 任务ID
            invoke_from (InvokeFrom): 调用来源，包括WEB_APP、DEBUGGER等
            user_id (UUID): 用户ID

        Returns:
            None

        该方法会：
        1. 检查任务是否已有停止标志
        2. 验证当前用户是否有权限操作此任务
        3. 如果验证通过，设置停止标志，过期时间为600秒

        """
        # 导入依赖注入器
        from app.http.module import injector

        # 获取Redis客户端实例
        redis_client = injector.get(Redis)

        # 获取当前任务的停止标志缓存键对应的值
        result = redis_client.get(cls.generate_task_stopped_cache_key(task_id))
        # 如果不存在停止标志，直接返回
        if not result:
            return

        # 根据调用来源确定用户前缀
        # WEB_APP和DEBUGGER使用"account"前缀
        # 其他来源使用"end-user"前缀
        user_prefix = (
            "account"
            if invoke_from in [InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER]
            else "end-user"
        )
        # 验证当前用户是否有权限操作此任务
        # 比较缓存中的用户标识与当前用户标识是否匹配
        if result.decode("utf-8") != f"{user_prefix}-{user_id!s}":
            return

        # 生成任务停止标志的缓存键
        stopped_cache_key = cls.generate_task_stopped_cache_key(task_id)
        # 设置停止标志，过期时间为600秒（10分钟）
        redis_client.setex(stopped_cache_key, 600, 1)
