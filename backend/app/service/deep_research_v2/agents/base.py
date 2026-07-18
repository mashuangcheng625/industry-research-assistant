"""
DeepResearch V2.0 - Agent 基类

所有专家Agent的基类，提供通用的LLM调用、日志记录等功能。
"""

import json
import logging
import asyncio
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from openai import OpenAI

from core.metrics import LLM_CALLS, LLM_DURATION, LLM_TOKENS
from ..state import ResearchState, AgentLog

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')


class BaseAgent(ABC):
    """
    Agent 基类

    所有专家Agent继承此类，实现特定的 process 方法。
    """

    def __init__(
        self,
        name: str,
        role: str,
        llm_api_key: str,
        llm_base_url: str,
        model: str = "qwen-max"
    ):
        self.name = name
        self.role = role
        self.model = model
        self.llm_base_url = llm_base_url
        request_timeout = max(
            1.0,
            float(os.getenv("AGENT_LLM_REQUEST_TIMEOUT_SECONDS", "120")),
        )
        max_retries = max(0, int(os.getenv("AGENT_LLM_MAX_RETRIES", "1")))
        self.client = OpenAI(
            api_key=llm_api_key,
            base_url=llm_base_url,
            timeout=request_timeout,
            max_retries=max_retries,
        )
        self.logger = logging.getLogger(f"Agent.{name}")

    def _effective_max_tokens(self, requested_max_tokens: int) -> int:
        """根据当前模型路由限制 Agent 的最大输出长度。

        本地小模型的上下文窗口通常小于云端模型。如果仍使用
        Writer 等 Agent 声明的 16000 token 上限，Ollama 可能会拒绝
        请求或长时间无法完成。

        注意：DeepSeek V4-Pro 等推理模型会在 max_tokens 内消耗
        reasoning_tokens。如果允许的预算太小，可见输出可能为零。
        因此云端推理模型推荐 CLOUD_LLM_MAX_OUTPUT_TOKENS >= 8192。
        """
        is_local_endpoint = any(
            marker in (self.llm_base_url or "").lower()
            for marker in ("127.0.0.1", "localhost", "host.docker.internal")
        )
        routing_mode = os.getenv("MODEL_ROUTING_MODE", "local").lower()
        is_local = is_local_endpoint or routing_mode == "local"

        if is_local:
            configured = os.getenv(
                "AGENT_MAX_OUTPUT_TOKENS",
                os.getenv("LOCAL_LLM_MAX_OUTPUT_TOKENS", "2048"),
            )
        else:
            configured = os.getenv("AGENT_MAX_OUTPUT_TOKENS")

        if not configured:
            return max(1, requested_max_tokens)

        try:
            configured_limit = max(1, int(configured))
        except (TypeError, ValueError):
            self.logger.warning(
                "Invalid AGENT/LLM max output token setting %r; using requested value %s",
                configured,
                requested_max_tokens,
            )
            return max(1, requested_max_tokens)

        return min(max(1, requested_max_tokens), configured_limit)

    @abstractmethod
    async def process(self, state: ResearchState) -> ResearchState:
        """
        处理状态并返回更新后的状态

        Args:
            state: 当前研究状态

        Returns:
            更新后的状态
        """
        pass

    async def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        temperature: float = 0.3,
        max_tokens: int = 16000  # 拉满到最大值
    ) -> str:
        """
        调用 LLM

        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示
            json_mode: 是否强制JSON输出
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            LLM 响应文本
        """
        start_time = time.perf_counter()
        outcome = "error"

        try:
            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": self._effective_max_tokens(max_tokens)
            }

            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                **kwargs
            )

            content = response.choices[0].message.content or ""
            duration = int((time.perf_counter() - start_time) * 1000)
            outcome = "success"

            usage = getattr(response, "usage", None)
            if usage is not None:
                for token_type, attribute in (
                    ("prompt", "prompt_tokens"),
                    ("completion", "completion_tokens"),
                ):
                    count = int(getattr(usage, attribute, 0) or 0)
                    if count > 0:
                        LLM_TOKENS.labels(
                            agent=self.name,
                            model=self.model,
                            token_type=token_type,
                        ).inc(count)

            self.logger.info(f"LLM call completed in {duration}ms, response length: {len(content)}")

            return content

        except asyncio.CancelledError:
            outcome = "cancelled"
            self.logger.info("LLM call cancelled")
            raise
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            raise
        finally:
            elapsed = max(0.0, time.perf_counter() - start_time)
            LLM_CALLS.labels(
                agent=self.name,
                model=self.model,
                outcome=outcome,
            ).inc()
            LLM_DURATION.labels(
                agent=self.name,
                model=self.model,
                outcome=outcome,
            ).observe(elapsed)

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """安全解析JSON响应，处理markdown代码块和格式问题"""
        import re

        def fix_escaped_newlines(s: str) -> str:
            """修复过度转义的换行符"""
            # 处理多层转义: \\\\n -> \n, \\n -> \n
            s = s.replace('\\\\\\\\n', '\n')
            s = s.replace('\\\\n', '\n')
            # 处理可能的 \\r\\n
            s = s.replace('\\\\\\\\r', '\r')
            s = s.replace('\\\\r', '\r')
            return s

        def try_parse(s: str) -> Optional[Dict]:
            """尝试解析JSON，包含修复逻辑"""
            # 清理常见问题
            s = s.strip()
            # 移除可能的BOM
            if s.startswith('\ufeff'):
                s = s[1:]

            try:
                result = json.loads(s)
                # 成功解析后，修复值中的转义字符
                return self._fix_escaped_values(result)
            except json.JSONDecodeError:
                pass

            # 尝试修复常见JSON问题
            try:
                # 修复无效的JSON转义序列 \[ \] \# 等 (LLM经常产生这种错误)
                # 需要在字符串值中修复，但避免影响已转义的反斜杠
                # \\[ 是有效的(表示 \[ 字面量)，但 \[ 不是有效的JSON转义
                s = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', '', s)
                # 移除注释
                s = re.sub(r'//.*?$', '', s, flags=re.MULTILINE)
                s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
                # 修复尾随逗号
                s = re.sub(r',(\s*[}\]])', r'\1', s)
                # 修复缺少逗号的情况（在 } 或 ] 后面缺少逗号）
                s = re.sub(r'([}\]])(\s*)([{\[])', r'\1,\2\3', s)
                # 修复没有引号的key
                s = re.sub(r'(\{|\,)\s*(\w+)\s*:', r'\1"\2":', s)
                result = json.loads(s)
                return self._fix_escaped_values(result)
            except json.JSONDecodeError:
                pass

            return None

        # 1. 先尝试直接解析
        result = try_parse(response)
        if result:
            self.logger.debug("Direct JSON parse succeeded")
            return result

        # 2. 尝试提取markdown代码块
        code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(code_block_pattern, response)
        if match:
            result = try_parse(match.group(1))
            if result:
                self.logger.debug("Extracted JSON from code block")
                return result

        # 3. 尝试找到最外层的 {...}
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1 and end > start:
            result = try_parse(response[start:end+1])
            if result:
                self.logger.debug("Extracted JSON from braces")
                return result

        # 4. 最后尝试用更宽松的方式解析
        try:
            # 使用 ast.literal_eval 作为备选
            import ast
            # 将 true/false/null 转换为 Python 格式
            s = response
            s = re.sub(r'\btrue\b', 'True', s)
            s = re.sub(r'\bfalse\b', 'False', s)
            s = re.sub(r'\bnull\b', 'None', s)
            start = s.find('{')
            end = s.rfind('}')
            if start != -1 and end != -1:
                result = ast.literal_eval(s[start:end+1])
                if isinstance(result, dict):
                    self.logger.debug("Parsed using ast.literal_eval")
                    return result
        except:
            pass

        self.logger.error(f"JSON parse error, could not extract valid JSON")
        self.logger.warning(f"Raw response (first 800 chars): {response[:800]}")
        return {}

    def _fix_escaped_values(self, obj: Any, key: str = None) -> Any:
        """
        递归修复字典和列表中的转义字符

        注意：对于 'code' 字段，不处理转义，因为代码中的 \n 是有意义的转义序列
        """
        if isinstance(obj, dict):
            return {k: self._fix_escaped_values(v, key=k) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._fix_escaped_values(item, key=key) for item in obj]
        elif isinstance(obj, str):
            # 对于代码字段，不进行转义处理
            # 因为代码中的 \n 应该保持为 \n（两个字符），而不是真正的换行
            if key in ('code', 'fixed_code', 'revised_content'):
                return obj

            # 对于其他字段，修复过度转义的换行符
            result = obj
            result = result.replace('\\\\n', '\n')
            result = result.replace('\\n', '\n')
            result = result.replace('\\\\r', '\r')
            result = result.replace('\\r', '\r')
            result = result.replace('\\\\t', '\t')
            result = result.replace('\\t', '\t')
            return result
        else:
            return obj

    def add_message(self, state: ResearchState, event_type: str, content: Any) -> None:
        """
        添加消息到状态（用于SSE流式输出）

        Args:
            state: 研究状态
            event_type: 事件类型
            content: 消息内容
        """
        message = {
            "type": event_type,
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "content": content
        }
        state["messages"].append(message)

        # 如果有消息队列，立即推送（支持实时流式输出）
        if "_message_queue" in state and state["_message_queue"] is not None:
            try:
                state["_message_queue"].put_nowait(message)
                self.logger.info(f"[SSE] Queued event: {event_type} (queue size: {state['_message_queue'].qsize()})")
            except Exception as e:
                self.logger.warning(f"Failed to push message to queue: {e}")
        else:
            self.logger.warning(f"[SSE] No queue available for event: {event_type}")

    def add_log(
        self,
        state: ResearchState,
        action: str,
        input_summary: str,
        output_summary: str,
        duration_ms: int,
        tokens_used: int = 0
    ) -> None:
        """添加执行日志"""
        log = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "action": action,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "duration_ms": duration_ms,
            "tokens_used": tokens_used
        }
        state["logs"].append(log)


class AgentRegistry:
    """Agent 注册表"""

    _agents: Dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, agent: BaseAgent) -> None:
        """注册Agent"""
        cls._agents[agent.name] = agent

    @classmethod
    def get(cls, name: str) -> Optional[BaseAgent]:
        """获取Agent"""
        return cls._agents.get(name)

    @classmethod
    def all(cls) -> Dict[str, BaseAgent]:
        """获取所有Agent"""
        return cls._agents.copy()
