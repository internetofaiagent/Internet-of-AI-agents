#!/usr/bin/env python3
"""
仲裁 Agent - 处理交易纠纷和仲裁请求
"""

import os
import json
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

# --- A2A 库导入 ---
from python_a2a import A2AServer, run_server, AgentCard, AgentSkill, TaskStatus, TaskState, A2AClient

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ArbitrationAgent")


# ==============================================================================
#  数据模型
# ==============================================================================
class ArbitrationStatus(Enum):
    """仲裁状态枚举"""
    PENDING = "pending"              # 待处理
    PROCESSING = "processing"        # 处理中
    DECIDED = "decided"              # 已裁定
    AGREED = "agreed"                # 双方同意
    EXECUTED = "executed"            # 已执行
    ESCALATED = "escalated"          # 已升级为人工仲裁


class ArbitrationDecision(Enum):
    """仲裁裁定结果枚举"""
    SUPPORT_USER = "support_user"           # 支持用户
    SUPPORT_MERCHANT = "support_merchant"   # 支持商家
    PARTIAL_SUPPORT = "partial_support"      # 部分支持（双方各承担部分责任）


@dataclass
class ArbitrationCase:
    """仲裁案例数据模型"""
    case_id: str
    order_id: str
    user_agent_url: str
    merchant_agent_url: str
    dispute_description: str
    order_info: Dict[str, Any]
    status: ArbitrationStatus = ArbitrationStatus.PENDING
    decision: Optional[ArbitrationDecision] = None
    decision_reason: Optional[str] = None
    responsible_party: Optional[str] = None  # "user" or "merchant"
    user_agreed: bool = False
    merchant_agreed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    decided_at: Optional[str] = None
    executed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "case_id": self.case_id,
            "order_id": self.order_id,
            "user_agent_url": self.user_agent_url,
            "merchant_agent_url": self.merchant_agent_url,
            "dispute_description": self.dispute_description,
            "order_info": self.order_info,
            "status": self.status.value,
            "decision": self.decision.value if self.decision else None,
            "decision_reason": self.decision_reason,
            "responsible_party": self.responsible_party,
            "user_agreed": self.user_agreed,
            "merchant_agreed": self.merchant_agreed,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "executed_at": self.executed_at
        }


# ==============================================================================
#  仲裁 Agent 服务器实现
# ==============================================================================
class ArbitrationAgent(A2AServer):
    """
    仲裁 Agent - 负责处理交易纠纷和仲裁请求
    """
    
    def __init__(self, agent_card: AgentCard):
        """初始化仲裁 Agent"""
        super().__init__(agent_card=agent_card)
        
        # 仲裁案例存储（在实际应用中应该使用数据库）
        self.cases: Dict[str, ArbitrationCase] = {}
        
        # 仲裁状态显示映射
        self.STATUS_DISPLAY = {
            ArbitrationStatus.PENDING.value: "待处理",
            ArbitrationStatus.PROCESSING.value: "处理中",
            ArbitrationStatus.DECIDED.value: "已裁定",
            ArbitrationStatus.AGREED.value: "双方同意",
            ArbitrationStatus.EXECUTED.value: "已执行",
            ArbitrationStatus.ESCALATED.value: "已升级为人工仲裁"
        }
        
        logger.info("✅ [ArbitrationAgent] 仲裁 Agent 初始化完成")
    
    def handle_task(self, task):
        """处理 A2A 任务"""
        text = task.message.get("content", {}).get("text", "")
        logger.info(f"📩 [ArbitrationAgent] 收到请求: '{text[:100]}...'")
        
        try:
            # 尝试解析 JSON 格式的请求
            try:
                request_data = json.loads(text)
                request_type = request_data.get("type", "")
                
                if request_type == "initiate_arbitration":
                    # 处理仲裁请求
                    result = self.initiate_arbitration(request_data)
                    response_text = json.dumps(result, ensure_ascii=False, indent=2)
                elif request_type == "process_dispute":
                    # 处理纠纷
                    case_id = request_data.get("case_id")
                    if case_id:
                        result = self.process_dispute(case_id)
                        response_text = json.dumps(result, ensure_ascii=False, indent=2)
                    else:
                        response_text = json.dumps({
                            "success": False,
                            "error": "缺少必需字段: case_id"
                        }, ensure_ascii=False, indent=2)
                elif request_type == "confirm_decision":
                    # 处理确认请求
                    case_id = request_data.get("case_id")
                    party = request_data.get("party")  # "user" or "merchant"
                    agreed = request_data.get("agreed", True)  # True表示同意，False表示不同意
                    
                    if case_id and party:
                        result = self.confirm_decision(case_id, party, agreed)
                        response_text = json.dumps(result, ensure_ascii=False, indent=2)
                    else:
                        response_text = json.dumps({
                            "success": False,
                            "error": "缺少必需字段: case_id 或 party"
                        }, ensure_ascii=False, indent=2)
                elif request_type == "check_timeout":
                    # 检查确认超时
                    case_id = request_data.get("case_id")
                    if case_id:
                        result = self.check_confirmation_timeout(case_id)
                        response_text = json.dumps(result, ensure_ascii=False, indent=2)
                    else:
                        response_text = json.dumps({
                            "success": False,
                            "error": "缺少必需字段: case_id"
                        }, ensure_ascii=False, indent=2)
                elif request_type == "execute_decision":
                    # 执行仲裁结果
                    case_id = request_data.get("case_id")
                    if case_id:
                        result = self.execute_decision(case_id)
                        response_text = json.dumps(result, ensure_ascii=False, indent=2)
                    else:
                        response_text = json.dumps({
                            "success": False,
                            "error": "缺少必需字段: case_id"
                        }, ensure_ascii=False, indent=2)
                else:
                    response_text = f"未知的请求类型: {request_type}"
                    task.status = TaskStatus(state=TaskState.FAILED)
            except json.JSONDecodeError:
                # 如果不是 JSON，尝试文本解析
                text_lower = text.lower()
                if any(keyword in text_lower for keyword in ["仲裁", "arbitration", "纠纷", "dispute"]):
                    # 尝试从文本中提取信息
                    response_text = self._handle_text_arbitration_request(text)
                else:
                    response_text = "请提供有效的仲裁请求。支持格式：JSON 或包含'仲裁'、'纠纷'关键词的文本。"
                    task.status = TaskStatus(state=TaskState.FAILED)
            
            task.status = TaskStatus(state=TaskState.COMPLETED)
            logger.info("✅ [ArbitrationAgent] 处理完成")
            
        except Exception as e:
            import traceback
            logger.error(f"❌ [ArbitrationAgent] 任务处理时发生错误: {e}")
            traceback.print_exc()
            response_text = f"服务器内部错误: {e}"
            task.status = TaskStatus(state=TaskState.FAILED)
        
        # 将最终结果打包成 A2A 响应
        task.artifacts = [{"parts": [{"type": "text", "text": str(response_text)}]}]
        return task
    
    def initiate_arbitration(
        self,
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        接收仲裁请求
        
        Args:
            request_data: 仲裁请求数据，包含：
                - order_id: 订单ID
                - user_agent_url: 用户 Agent URL
                - merchant_agent_url: 商家 Agent URL
                - dispute_description: 纠纷描述
                - order_info: 订单信息（可选）
        
        Returns:
            包含处理结果的字典
        """
        logger.info("📋 [ArbitrationAgent] 接收仲裁请求")
        
        try:
            # 验证必需字段
            order_id = request_data.get("order_id")
            user_agent_url = request_data.get("user_agent_url")
            merchant_agent_url = request_data.get("merchant_agent_url")
            dispute_description = request_data.get("dispute_description", "")
            
            if not order_id:
                return {
                    "success": False,
                    "error": "缺少必需字段: order_id"
                }
            
            if not user_agent_url:
                return {
                    "success": False,
                    "error": "缺少必需字段: user_agent_url"
                }
            
            if not merchant_agent_url:
                return {
                    "success": False,
                    "error": "缺少必需字段: merchant_agent_url"
                }
            
            # 检查是否已有该订单的仲裁案例
            existing_case = None
            for case in self.cases.values():
                if case.order_id == order_id:
                    existing_case = case
                    break
            
            if existing_case:
                logger.warning(f"⚠️ [ArbitrationAgent] 订单 {order_id} 已有仲裁案例: {existing_case.case_id}")
                return {
                    "success": False,
                    "error": f"该订单已有仲裁案例: {existing_case.case_id}",
                    "existing_case_id": existing_case.case_id,
                    "existing_status": existing_case.status.value
                }
            
            # 生成仲裁案例ID
            case_id = f"ARB_{int(time.time())}_{order_id[:8]}"
            
            # 获取订单信息（如果提供）
            order_info = request_data.get("order_info", {})
            
            # 创建仲裁案例
            case = ArbitrationCase(
                case_id=case_id,
                order_id=order_id,
                user_agent_url=user_agent_url,
                merchant_agent_url=merchant_agent_url,
                dispute_description=dispute_description,
                order_info=order_info,
                status=ArbitrationStatus.PENDING
            )
            
            # 存储案例
            self.cases[case_id] = case
            
            logger.info(f"✅ [ArbitrationAgent] 仲裁案例已创建: {case_id}, 订单: {order_id}")
            
            # 返回成功结果
            return {
                "success": True,
                "case_id": case_id,
                "order_id": order_id,
                "status": case.status.value,
                "status_display": self.STATUS_DISPLAY.get(case.status.value, case.status.value),
                "message": f"仲裁请求已接收，案例ID: {case_id}",
                "created_at": case.created_at
            }
            
        except Exception as e:
            logger.error(f"❌ [ArbitrationAgent] 接收仲裁请求失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"接收仲裁请求失败: {str(e)}"
            }
    
    def _handle_text_arbitration_request(self, text: str) -> str:
        """处理文本格式的仲裁请求（简化版）"""
        try:
            # 尝试从文本中提取订单ID
            import re
            order_match = re.search(r'订单[号]*[:\s]*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
            if not order_match:
                order_match = re.search(r'order[_\s]*id[:\s]*([A-Za-z0-9_-]+)', text, re.IGNORECASE)
            
            if not order_match:
                return "无法从请求中提取订单ID，请提供有效的订单ID。"
            
            order_id = order_match.group(1)
            
            # 构建简化的请求数据
            request_data = {
                "type": "initiate_arbitration",
                "order_id": order_id,
                "user_agent_url": "http://localhost:5011",  # 默认值
                "merchant_agent_url": "http://localhost:5020",  # 默认值
                "dispute_description": text
            }
            
            result = self.initiate_arbitration(request_data)
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return f"处理文本请求失败: {str(e)}"
    
    def process_dispute(
        self,
        case_id: str
    ) -> Dict[str, Any]:
        """
        处理纠纷（基于订单信息做简单判断 - 简化版）
        
        判断逻辑：
        - 未发货（PENDING/ACCEPTED/PROCESSING）→ 支持用户
        - 已发货但未确认收货（DELIVERED）→ 需要更多信息
        - 已确认收货（COMPLETED）→ 支持商家
        
        Args:
            case_id: 仲裁案例ID
        
        Returns:
            包含处理结果的字典
        """
        logger.info(f"🔍 [ArbitrationAgent] 开始处理纠纷: {case_id}")
        
        try:
            # 获取仲裁案例
            case = self.cases.get(case_id)
            if not case:
                return {
                    "success": False,
                    "error": f"仲裁案例不存在: {case_id}"
                }
            
            # 检查案例状态
            if case.status != ArbitrationStatus.PENDING:
                return {
                    "success": False,
                    "error": f"案例状态不允许处理，当前状态: {case.status.value}",
                    "current_status": case.status.value
                }
            
            # 更新状态为处理中
            case.status = ArbitrationStatus.PROCESSING
            logger.info(f"📋 [ArbitrationAgent] 案例状态更新为: {case.status.value}")
            
            # 从订单信息中提取状态
            order_info = case.order_info
            order_status = order_info.get("status", "").upper() if isinstance(order_info, dict) else ""
            
            # 如果没有订单状态，尝试从其他字段推断
            if not order_status:
                # 检查是否有交付信息
                delivery_info = order_info.get("delivery_info", {}) if isinstance(order_info, dict) else {}
                if delivery_info and delivery_info.get("delivery_status"):
                    order_status = "DELIVERED"
                elif order_info.get("accepted_at") if isinstance(order_info, dict) else False:
                    order_status = "ACCEPTED"
                else:
                    order_status = "PENDING"
            
            # 调用 make_decision 做出裁定
            decision_result = self.make_decision(case_id, order_info, order_status)
            
            if not decision_result.get("success"):
                # 如果裁定失败，恢复状态
                case.status = ArbitrationStatus.PENDING
                return decision_result
            
            if not decision_result.get("success"):
                # 如果裁定失败，恢复状态
                case.status = ArbitrationStatus.PENDING
                return decision_result
            
            # 更新案例信息
            case.decision = decision_result["decision"]
            case.decision_reason = decision_result["decision_reason"]
            case.responsible_party = decision_result["responsible_party"]
            case.status = ArbitrationStatus.DECIDED
            case.decided_at = datetime.now().isoformat()
            
            logger.info(f"✅ [ArbitrationAgent] 纠纷处理完成: {case_id}, 裁定: {decision_result['decision'].value}")
            
            # 返回处理结果
            return {
                "success": True,
                "case_id": case_id,
                "order_id": case.order_id,
                "order_status": order_status,
                "decision": decision_result["decision"].value,
                "decision_reason": decision_result["decision_reason"],
                "responsible_party": decision_result["responsible_party"],
                "status": case.status.value,
                "status_display": self.STATUS_DISPLAY.get(case.status.value, case.status.value),
                "decided_at": case.decided_at,
                "message": f"纠纷处理完成，裁定结果: {decision_result['decision'].value}"
            }
            
        except Exception as e:
            logger.error(f"❌ [ArbitrationAgent] 处理纠纷失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 如果案例存在，恢复状态
            if case_id in self.cases:
                case = self.cases[case_id]
                case.status = ArbitrationStatus.PENDING
            
            return {
                "success": False,
                "error": f"处理纠纷失败: {str(e)}",
                "case_id": case_id
            }
    
    def make_decision(
        self,
        case_id: str,
        order_info: Dict[str, Any],
        order_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        做出简单裁定（支持用户/支持商家/部分支持）
        
        基于订单状态做出简单仲裁裁定：
        - 未发货（PENDING/ACCEPTED/PROCESSING）→ 支持用户
        - 已发货但未确认收货（DELIVERED）→ 需要更多信息（部分支持）
        - 已确认收货（COMPLETED）→ 支持商家
        
        Args:
            case_id: 仲裁案例ID
            order_info: 订单信息字典
            order_status: 订单状态（可选，如果不提供则从order_info中提取）
        
        Returns:
            包含简单裁定结果的字典：
                - success: 是否成功
                - decision: 裁定结果（ArbitrationDecision枚举：SUPPORT_USER, SUPPORT_MERCHANT, PARTIAL_SUPPORT）
                - decision_reason: 裁定原因说明
                - responsible_party: 责任方（"user", "merchant", "both"）
                - order_status: 订单状态
        """
        logger.info(f"⚖️ [ArbitrationAgent] 开始做出裁定: {case_id}")
        
        try:
            # 如果没有提供订单状态，从order_info中提取
            if not order_status:
                order_status = order_info.get("status", "").upper() if isinstance(order_info, dict) else ""
                
                # 如果还是没有，尝试推断
                if not order_status:
                    delivery_info = order_info.get("delivery_info", {}) if isinstance(order_info, dict) else {}
                    if delivery_info and delivery_info.get("delivery_status"):
                        order_status = "DELIVERED"
                    elif order_info.get("accepted_at") if isinstance(order_info, dict) else False:
                        order_status = "ACCEPTED"
                    else:
                        order_status = "PENDING"
            
            # 基于订单状态做简单判断（简化版）
            decision = None
            decision_reason = ""
            responsible_party = None
            
            if order_status in ["PENDING", "ACCEPTED", "PROCESSING"]:
                # 未发货 → 支持用户
                decision = ArbitrationDecision.SUPPORT_USER
                decision_reason = f"订单状态为 {order_status}（未发货），商家未履行发货义务，支持用户退款请求。"
                responsible_party = "merchant"
                logger.info(f"✅ [ArbitrationAgent] 判断结果: 支持用户（未发货）")
                
            elif order_status == "DELIVERED":
                # 已发货但未确认收货 → 需要更多信息
                decision = ArbitrationDecision.PARTIAL_SUPPORT
                decision_reason = "订单已发货但用户未确认收货，需要更多信息（交付证明、用户反馈等）来判断。"
                responsible_party = "both"
                logger.info(f"✅ [ArbitrationAgent] 判断结果: 部分支持（需要更多信息）")
                    
            elif order_status == "COMPLETED":
                # 已确认收货 → 支持商家
                decision = ArbitrationDecision.SUPPORT_MERCHANT
                decision_reason = f"订单状态为 {order_status}（已确认收货），用户已确认收到商品，支持商家，驳回用户退款请求。"
                responsible_party = "user"
                logger.info(f"✅ [ArbitrationAgent] 判断结果: 支持商家（已确认收货）")
                
            else:
                # 其他状态（如CANCELLED等）→ 需要更多信息
                decision = ArbitrationDecision.PARTIAL_SUPPORT
                decision_reason = f"订单状态为 {order_status}，需要更多信息（订单详情、取消原因等）来判断。"
                responsible_party = "both"
                logger.info(f"✅ [ArbitrationAgent] 判断结果: 部分支持（需要更多信息）")
            
            # 确保所有变量都已赋值
            if decision is None:
                decision = ArbitrationDecision.PARTIAL_SUPPORT
                decision_reason = "无法确定订单状态，需要更多信息来判断。"
                responsible_party = "both"
            
            logger.info(f"✅ [ArbitrationAgent] 裁定完成: {case_id}, 裁定结果: {decision.value}")
            
            # 返回简单裁定结果（不更新案例状态，由调用者负责更新）
            return {
                "success": True,
                "decision": decision,  # ArbitrationDecision枚举：SUPPORT_USER, SUPPORT_MERCHANT, PARTIAL_SUPPORT
                "decision_reason": decision_reason,  # 裁定原因说明
                "responsible_party": responsible_party,  # 责任方："user", "merchant", "both"
                "order_status": order_status  # 订单状态
            }
            
        except Exception as e:
            logger.error(f"❌ [ArbitrationAgent] 做出裁定失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": f"做出裁定失败: {str(e)}",
                "case_id": case_id
            }
    
    def notify_parties(
        self,
        case_id: str,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        通知双方裁定结果
        
        向用户Agent和商家Agent发送仲裁裁定结果通知，等待双方确认。
        
        Args:
            case_id: 仲裁案例ID
            max_retries: 最大重试次数（默认3次）
            retry_delay: 重试延迟（秒，默认1.0秒）
        
        Returns:
            包含通知结果的字典：
                - success: 是否成功
                - user_notified: 用户是否已通知
                - merchant_notified: 商家是否已通知
                - user_response: 用户Agent响应
                - merchant_response: 商家Agent响应
        """
        logger.info(f"📢 [ArbitrationAgent] 开始通知双方裁定结果: {case_id}")
        
        try:
            # 获取仲裁案例
            case = self.cases.get(case_id)
            if not case:
                return {
                    "success": False,
                    "error": f"仲裁案例不存在: {case_id}"
                }
            
            # 检查案例是否已裁定
            if case.status != ArbitrationStatus.DECIDED:
                return {
                    "success": False,
                    "error": f"案例尚未裁定，当前状态: {case.status.value}",
                    "current_status": case.status.value
                }
            
            if not case.decision:
                return {
                    "success": False,
                    "error": "案例没有裁定结果"
                }
            
            # 构建通知消息
            decision_display = {
                ArbitrationDecision.SUPPORT_USER: "支持用户",
                ArbitrationDecision.SUPPORT_MERCHANT: "支持商家",
                ArbitrationDecision.PARTIAL_SUPPORT: "部分支持"
            }.get(case.decision, case.decision.value)
            
            notification_message = f"""⚖️ **仲裁裁定结果通知**

**案例信息**：
- 案例ID: {case.case_id}
- 订单ID: {case.order_id}
- 纠纷描述: {case.dispute_description}

**裁定结果**：
- 裁定: {decision_display}
- 裁定原因: {case.decision_reason or '无'}
- 责任方: {case.responsible_party or '未确定'}

**后续步骤**：
请确认是否同意此裁定结果。双方都同意后，将执行仲裁结果。

**重要提示**：
- 如果一方不同意，可以申请升级为人工仲裁
- 确认期限：24小时
- 逾期未确认将视为默认同意

请回复"同意"或"不同意"以确认裁定结果。"""
            
            # 通知结果
            user_notified = False
            merchant_notified = False
            user_response = None
            merchant_response = None
            user_error = None
            merchant_error = None
            
            # 通知用户Agent
            if case.user_agent_url:
                user_result = self._notify_agent(
                    agent_url=case.user_agent_url,
                    notification_text=notification_message,
                    agent_type="用户",
                    max_retries=max_retries,
                    retry_delay=retry_delay
                )
                user_notified = user_result.get("success", False)
                user_response = user_result.get("response")
                if not user_notified:
                    user_error = user_result.get("error")
                    logger.warning(f"⚠️ [ArbitrationAgent] 通知用户Agent失败: {user_error}")
            else:
                logger.warning(f"⚠️ [ArbitrationAgent] 用户Agent URL为空，跳过通知")
            
            # 通知商家Agent
            if case.merchant_agent_url:
                merchant_result = self._notify_agent(
                    agent_url=case.merchant_agent_url,
                    notification_text=notification_message,
                    agent_type="商家",
                    max_retries=max_retries,
                    retry_delay=retry_delay
                )
                merchant_notified = merchant_result.get("success", False)
                merchant_response = merchant_result.get("response")
                if not merchant_notified:
                    merchant_error = merchant_result.get("error")
                    logger.warning(f"⚠️ [ArbitrationAgent] 通知商家Agent失败: {merchant_error}")
            else:
                logger.warning(f"⚠️ [ArbitrationAgent] 商家Agent URL为空，跳过通知")
            
            # 判断整体是否成功（至少一方通知成功）
            overall_success = user_notified or merchant_notified
            
            if overall_success:
                logger.info(f"✅ [ArbitrationAgent] 通知完成: 用户={user_notified}, 商家={merchant_notified}")
            else:
                logger.error(f"❌ [ArbitrationAgent] 通知失败: 用户和商家都未成功通知")
            
            return {
                "success": overall_success,
                "case_id": case_id,
                "order_id": case.order_id,
                "user_notified": user_notified,
                "merchant_notified": merchant_notified,
                "user_response": user_response,
                "merchant_response": merchant_response,
                "user_error": user_error,
                "merchant_error": merchant_error,
                "message": f"通知完成: 用户={'成功' if user_notified else '失败'}, 商家={'成功' if merchant_notified else '失败'}"
            }
            
        except Exception as e:
            logger.error(f"❌ [ArbitrationAgent] 通知双方失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"通知双方失败: {str(e)}",
                "case_id": case_id
            }
    
    def _notify_agent(
        self,
        agent_url: str,
        notification_text: str,
        agent_type: str,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        通知单个Agent（内部方法，支持重试）
        
        Args:
            agent_url: Agent URL
            notification_text: 通知文本
            agent_type: Agent类型（用于日志）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        
        Returns:
            包含通知结果的字典
        """
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔄 [ArbitrationAgent] 尝试通知{agent_type}Agent (第 {attempt}/{max_retries} 次): {agent_url}")
                
                # 使用 A2AClient 连接Agent
                client = A2AClient(agent_url)
                
                # 发送通知
                response = client.ask(notification_text)
                
                logger.info(f"📥 [ArbitrationAgent] 收到{agent_type}Agent响应: {response[:200] if response else 'None'}...")
                
                # 尝试解析响应（可能是 JSON 格式或文本格式）
                try:
                    # 尝试解析 JSON 格式的响应
                    if "{" in response and "}" in response:
                        start = response.find("{")
                        end = response.rfind("}") + 1
                        json_str = response[start:end]
                        parsed_response = json.loads(json_str)
                        
                        if parsed_response.get("success") or parsed_response.get("status") in ["received", "agreed", "disagreed"]:
                            logger.info(f"✅ [ArbitrationAgent] {agent_type}Agent成功接收通知")
                            return {
                                "success": True,
                                "response": parsed_response,
                                "raw_response": response
                            }
                        else:
                            error_msg = parsed_response.get("error", "未知错误")
                            logger.warning(f"⚠️ [ArbitrationAgent] {agent_type}Agent返回错误: {error_msg}")
                            last_error = error_msg
                    else:
                        # 文本格式响应，认为成功
                        logger.info(f"✅ [ArbitrationAgent] {agent_type}Agent成功接收通知（文本响应）")
                        return {
                            "success": True,
                            "response": {"message": response},
                            "raw_response": response
                        }
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"⚠️ [ArbitrationAgent] 解析{agent_type}Agent响应失败: {e}")
                    # 即使解析失败，如果有响应也认为成功
                    if response:
                        return {
                            "success": True,
                            "response": {"message": response},
                            "raw_response": response
                        }
                    last_error = f"响应解析失败: {str(e)}"
                
            except Exception as e:
                last_error = f"连接{agent_type}Agent失败: {str(e)}"
                logger.warning(f"⚠️ [ArbitrationAgent] 第 {attempt} 次尝试失败: {last_error}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries:
                    time.sleep(retry_delay)
        
        # 所有重试都失败
        logger.error(f"❌ [ArbitrationAgent] 通知{agent_type}Agent失败（已重试{max_retries}次）")
            return {
                "success": False,
                "error": last_error or f"通知{agent_type}Agent失败"
        }
    
    def confirm_decision(
        self,
        case_id: str,
        party: str,  # "user" or "merchant"
        agreed: bool
    ) -> Dict[str, Any]:
        """
        接收一方对裁定结果的确认
        
        Args:
            case_id: 仲裁案例ID
            party: 确认方（"user" 或 "merchant"）
            agreed: 是否同意（True表示同意，False表示不同意）
        
        Returns:
            包含处理结果的字典
        """
        logger.info(f"📝 [ArbitrationAgent] 接收 {party} 的确认: case_id={case_id}, agreed={agreed}")
        
        try:
            # 获取仲裁案例
            case = self.cases.get(case_id)
            if not case:
                return {
                    "success": False,
                    "error": f"仲裁案例不存在: {case_id}"
                }
            
            # 检查案例状态
            if case.status != ArbitrationStatus.DECIDED:
                return {
                    "success": False,
                    "error": f"案例尚未裁定，当前状态: {case.status.value}",
                    "current_status": case.status.value
                }
            
            # 更新确认状态
            if party == "user":
                case.user_agreed = agreed
                logger.info(f"✅ [ArbitrationAgent] 用户确认: {'同意' if agreed else '不同意'}")
            elif party == "merchant":
                case.merchant_agreed = agreed
                logger.info(f"✅ [ArbitrationAgent] 商家确认: {'同意' if agreed else '不同意'}")
            else:
                return {
                    "success": False,
                    "error": f"无效的确认方: {party}，必须是 'user' 或 'merchant'"
                }
            
            # 检查双方确认状态
            if not agreed:
                # 一方不同意，标记为升级
                case.status = ArbitrationStatus.ESCALATED
                logger.info(f"⚠️ [ArbitrationAgent] {party} 不同意裁定结果，案例已标记为升级: {case_id}")
                
                return {
                    "success": True,
                    "case_id": case_id,
                    "party": party,
                    "agreed": False,
                    "status": case.status.value,
                    "message": f"{party} 不同意裁定结果，案例已标记为升级为人工仲裁",
                    "escalated": True
                }
            
            # 检查是否双方都同意
            if case.user_agreed and case.merchant_agreed:
                # 双方都同意，执行结果
                case.status = ArbitrationStatus.AGREED
                logger.info(f"✅ [ArbitrationAgent] 双方都同意，准备执行结果: {case_id}")
                
                # 执行结果
                execution_result = self.execute_decision(case_id)
                
                return {
                    "success": True,
                    "case_id": case_id,
                    "party": party,
                    "agreed": True,
                    "both_agreed": True,
                    "status": case.status.value,
                    "execution_result": execution_result,
                    "message": "双方都同意，仲裁结果已执行"
                }
            else:
                # 等待另一方确认
                waiting_for = "商家" if party == "user" else "用户"
                return {
                    "success": True,
                    "case_id": case_id,
                    "party": party,
                    "agreed": True,
                    "both_agreed": False,
                    "status": case.status.value,
                    "waiting_for": waiting_for,
                    "message": f"{party} 已同意，等待 {waiting_for} 确认"
                }
        
        except Exception as e:
            logger.error(f"❌ [ArbitrationAgent] 处理确认失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": f"处理确认失败: {str(e)}",
                "case_id": case_id
            }
    
    def check_confirmation_timeout(self, case_id: str) -> Dict[str, Any]:
        """
        检查确认超时（24小时）
        
        Args:
            case_id: 仲裁案例ID
        
        Returns:
            包含检查结果的字典
        """
        logger.info(f"⏰ [ArbitrationAgent] 检查确认超时: {case_id}")
        
        try:
            case = self.cases.get(case_id)
            if not case:
                return {
                    "success": False,
                    "error": f"仲裁案例不存在: {case_id}"
                }
            
            if case.status != ArbitrationStatus.DECIDED:
                return {
                    "success": False,
                    "error": f"案例状态不是 DECIDED，当前状态: {case.status.value}"
                }
            
            if not case.decided_at:
                return {
                    "success": False,
                    "error": "案例没有裁定时间，无法检查超时"
                }
            
            # 计算时间差
            from datetime import datetime, timedelta
            decided_time = datetime.fromisoformat(case.decided_at.replace('Z', '+00:00') if 'Z' in case.decided_at else case.decided_at)
            now = datetime.now()
            time_diff = now - decided_time.replace(tzinfo=None)
            
            # 24小时 = 86400秒
            timeout_seconds = 24 * 60 * 60
            is_timeout = time_diff.total_seconds() > timeout_seconds
            
            if is_timeout:
                logger.info(f"⏰ [ArbitrationAgent] 确认超时: {case_id}, 已过 {time_diff.total_seconds() / 3600:.1f} 小时")
                
                # 将未确认的一方视为默认同意
                if not case.user_agreed:
                    case.user_agreed = True
                    logger.info(f"✅ [ArbitrationAgent] 用户超时未确认，视为默认同意")
                
                if not case.merchant_agreed:
                    case.merchant_agreed = True
                    logger.info(f"✅ [ArbitrationAgent] 商家超时未确认，视为默认同意")
                
                # 如果双方都同意（包括默认同意），执行结果
                if case.user_agreed and case.merchant_agreed:
                    case.status = ArbitrationStatus.AGREED
                    execution_result = self.execute_decision(case_id)
                    
                    return {
                        "success": True,
                        "case_id": case_id,
                        "timeout": True,
                        "time_elapsed_hours": time_diff.total_seconds() / 3600,
                        "status": case.status.value,
                        "execution_result": execution_result,
                        "message": "确认超时，双方视为默认同意，仲裁结果已执行"
                    }
                else:
                    return {
                        "success": True,
                        "case_id": case_id,
                        "timeout": True,
                        "time_elapsed_hours": time_diff.total_seconds() / 3600,
                        "status": case.status.value,
                        "message": "确认超时，但仍有未确认方"
                    }
            else:
                remaining_hours = (timeout_seconds - time_diff.total_seconds()) / 3600
                return {
                    "success": True,
                    "case_id": case_id,
                    "timeout": False,
                    "remaining_hours": remaining_hours,
                    "user_agreed": case.user_agreed,
                    "merchant_agreed": case.merchant_agreed,
                    "message": f"尚未超时，剩余 {remaining_hours:.1f} 小时"
                }
        
        except Exception as e:
            logger.error(f"❌ [ArbitrationAgent] 检查超时失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": f"检查超时失败: {str(e)}",
                "case_id": case_id
            }
    
    def execute_decision(self, case_id: str) -> Dict[str, Any]:
        """
        执行仲裁结果
        
        Args:
            case_id: 仲裁案例ID
        
        Returns:
            包含执行结果的字典
        """
        logger.info(f"⚙️ [ArbitrationAgent] 开始执行仲裁结果: {case_id}")
        
        try:
            case = self.cases.get(case_id)
            if not case:
                return {
                    "success": False,
                    "error": f"仲裁案例不存在: {case_id}"
                }
            
            if case.status != ArbitrationStatus.AGREED:
                return {
                    "success": False,
                    "error": f"案例状态不是 AGREED，当前状态: {case.status.value}",
                    "current_status": case.status.value
                }
            
            if not case.decision:
                return {
                    "success": False,
                    "error": "案例没有裁定结果，无法执行"
                }
            
            # 更新状态为已执行
            case.status = ArbitrationStatus.EXECUTED
            case.executed_at = datetime.now().isoformat()
            
            logger.info(f"✅ [ArbitrationAgent] 仲裁结果已执行: {case_id}")
            logger.info(f"   裁定结果: {case.decision.value}")
            logger.info(f"   责任方: {case.responsible_party}")
            logger.info(f"   执行时间: {case.executed_at}")
            
            # 记录责任方（用于后续费用结算）
            # 责任方信息已记录在 case.responsible_party 中
            logger.info(f"📝 [ArbitrationAgent] 责任方已记录: {case.responsible_party} (费用结算后续实现)")
            
            # 根据裁定更新订单状态
            order_update_result = self._update_order_status(case)
            
            # 通知双方Agent执行结果
            notification_result = self._notify_execution_result(case)
            
            return {
                "success": True,
                "case_id": case_id,
                "order_id": case.order_id,
                "decision": case.decision.value,
                "responsible_party": case.responsible_party,  # 责任方已记录
                "executed_at": case.executed_at,
                "status": case.status.value,
                "order_update_result": order_update_result,
                "notification_result": notification_result,
                "message": f"仲裁结果已执行: {case.decision.value}, 责任方: {case.responsible_party}"
            }
        
        except Exception as e:
            logger.error(f"❌ [ArbitrationAgent] 执行结果失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": f"执行结果失败: {str(e)}",
                "case_id": case_id
            }
    
    def get_case(self, case_id: str) -> Optional[ArbitrationCase]:
        """获取仲裁案例"""
        return self.cases.get(case_id)
    
    def list_cases(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出仲裁案例"""
        cases = list(self.cases.values())
        
        if status:
            cases = [c for c in cases if c.status.value == status]
        
        return [case.to_dict() for case in cases]


# ==============================================================================
#  主函数和服务器启动
# ==============================================================================
def main():
    """启动仲裁 Agent 服务器"""
    import os
    
    # 配置端口
    port = int(os.getenv("ARBITRATION_AGENT_PORT", "5025"))
    
    # 创建 Agent Card
    agent_card = AgentCard(
        name="Arbitration Agent",
        description="第三方仲裁 Agent，负责处理交易纠纷和仲裁请求",
        url=f"http://localhost:{port}",
        skills=[
            AgentSkill(
                name="arbitration",
                description="处理交易纠纷和仲裁请求"
            ),
            AgentSkill(
                name="dispute_resolution",
                description="解决交易纠纷，做出仲裁裁定"
            )
        ]
    )
    
    # 创建并启动服务器
    agent = ArbitrationAgent(agent_card=agent_card)
    logger.info(f"🚀 [ArbitrationAgent] 启动仲裁 Agent 服务器，端口: {port}")
    run_server(agent, port=port)


if __name__ == "__main__":
    main()

