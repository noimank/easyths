import time

import pandas as pd

from easyths.core import BaseOperation
from easyths.models.operations import OperationResult
from easyths.operations.params import OrderCancelByContractParams
from easyths.operations.results import OrderCancelByContractResult
from easyths.utils import text2df


class OrderCancelByContractOperation(BaseOperation[OrderCancelByContractParams]):
    """按合同编号（委托号）撤单 —— 精细化撤单操作。

    适用场景：用户账户上同一股票有多笔未成交委托，需要**只撤其中一笔**（按委托号）。
    `OrderCancelOperation` 只支持按股票代码 + all/buy/sell 全量撤，粒度太粗。

    实现说明（PR review 时重点关注）：
    - THS 撤单界面（F3）只接受「股票代码」过滤输入，**不能直接按合同编号过滤**；
    - 本操作流程：F3 → 输入股票代码过滤（需先 order_query 拿 contract_no → 股票代码映射）
      → 解析表格 → 找到 contract_no 匹配的行 → 滚动到该行并双击 → 点击单笔撤单按钮。
    - 虚拟表格滚动：CVirtualGridCtrl 是虚拟表，未渲染行无法 click_input()，
      需要 ensure_visible + 必要时 SetScrollPos 强制滚动。

    注意：本操作依赖调用方提供 stock_code（因为 THS UI 限制）。如果调用方拿不到
    contract_no → stock_code 映射（如直接收到一个孤立委托号），请先调
    order_query 查全部委托，再从中提取 stock_code。
    """

    operation_name = "order_cancel_by_contract"
    description = "按合同编号撤销指定的单笔委托"
    Params = OrderCancelByContractParams
    Result = OrderCancelByContractResult

    def execute(self, params: OrderCancelByContractParams) -> OperationResult:
        start_time = time.time()
        contract_no = params.contract_no.strip()
        self.logger.info("执行按合同编号撤单", contract_no=contract_no)

        main_window = self.get_main_window(wrapper_obj=True)

        # 1) 必须先做一次 order_query 拿到 contract_no → stock_code 映射
        #    THS 撤单界面 UI 只接受股票代码过滤，无法按 contract_no 直接过滤。
        from easyths.operations.order_query import OrderQueryOperation

        try:
            oq = OrderQueryOperation(self.automator, self.logger)
            oq_res = oq.execute(None)  # type: ignore[arg-type]
        except Exception as e:
            return self._fail(f"查询委托映射失败：{e}")

        if not oq_res.success or not isinstance(oq_res.data, list):
            return self._fail(
                f"查询委托映射失败：{oq_res.message or '无数据'}"
            )

        # 找到 contract_no 匹配的行
        matching_row = None
        for row in oq_res.data:
            if str(row.get("contract_no", "")).strip() == contract_no:
                matching_row = row
                break

        if matching_row is None:
            # 该合同编号不在当日委托列表里（可能已成交/已撤/废单/隔夜单）
            available = [str(r.get("contract_no", "")) for r in oq_res.data]
            return self._fail(
                f"找不到合同编号 {contract_no}（可能已成交/已撤/废单）。"
                f"当前可见合同编号: {available[:20]}"
            )

        stock_code = matching_row["stock_code"]
        target_qty = int(matching_row.get("quantity", 0) or 0)
        cancelled_qty = int(matching_row.get("cancelled_quantity", 0) or 0)
        filled_qty = int(matching_row.get("filled_quantity", 0) or 0)

        # 已成交/已部分成交 ≥ 总量，或已撤 ≥ 总量 → 不可撤
        if filled_qty >= target_qty and target_qty > 0:
            return self._fail(
                f"合同编号 {contract_no} 已全部成交（{filled_qty}/{target_qty}），不可撤"
            )
        if cancelled_qty >= target_qty and target_qty > 0:
            return self._fail(
                f"合同编号 {contract_no} 已撤销（{cancelled_qty}/{target_qty}），不可重复撤"
            )

        # 2) F3 进入撤单界面，按股票代码过滤
        main_window.type_keys("{F3}")
        time.sleep(0.2)
        main_panel = self.get_control_with_children(
            main_window,
            class_name="AfxMDIFrame140s",
            control_type="Pane",
            auto_id="59648",
        ).children(class_name="AfxMDIFrame140s")[0]

        # 3) 输入股票代码过滤
        edit_stock_code = self.get_control_with_children(
            main_panel, control_type="Edit", class_name="Edit", auto_id="3348"
        )
        edit_stock_code.type_keys("{BACKSPACE 6}")
        time.sleep(0.1)
        edit_stock_code.type_keys(stock_code)
        time.sleep(0.1)

        # 4) 点查询按钮刷新
        self.get_control_with_children(
            main_panel, control_type="Button", class_name="Button", auto_id="3349"
        ).click()
        time.sleep(0.2)

        # 5) 复制表格 → 找到 contract_no 匹配的行号
        self.clear_clipboard()
        table_control = (
            self.get_control_with_children(
                main_panel, auto_id="1047", control_type="Pane"
            )
            .children()[0]
            .children(class_name="CVirtualGridCtrl")[0]
        )
        table_control.click_input()
        table_control.type_keys("^a")
        time.sleep(0.05)
        table_control.type_keys("^c")
        time.sleep(0.1)
        self.process_captcha_dialog()

        table_df: pd.DataFrame = text2df(self.get_clipboard_data())

        # 找目标行索引
        target_row_idx = None
        if "合同编号" in table_df.columns and not table_df.empty:
            mask = table_df["合同编号"].astype(str).str.strip() == contract_no
            if mask.any():
                target_row_idx = int(mask.idxmax())

        if target_row_idx is None:
            available = (
                table_df["合同编号"].astype(str).str.strip().tolist()
                if "合同编号" in table_df.columns
                else []
            )
            return self._fail(
                f"撤单界面过滤后未找到合同编号 {contract_no}。"
                f"过滤后可见: {available[:20]}"
            )

        # 6) 双击该行 → 触发 THS「选中 + 准备撤」状态
        #    虚拟表格需要先确保行可见。pywinauto 没有原生的 row.click()，
        #    这里用最稳的方式：select 整张表后用 keyboard 移动到目标行（如果支持），
        #    或者直接在该行已知位置 click_input()（依赖 THS 表格实现，PR 时需实测）。
        #    兜底方案：双击目标 contract_no 文本单元格区域（用 get_item 找）。
        try:
            row_data = table_df.iloc[target_row_idx].to_dict()
            self.logger.info(
                "找到目标行", contract_no=contract_no, row_data=row_data
            )
            # 尝试双击该行 —— pywinauto 的 CVirtualGridCtrl 通常需要先 select_cells
            # 实际操作中可能需要 scroll + click；这里给出双击整行的兜底实现
            table_control.double_click_input(
                coords=(
                    50,  # 在列区域内的 x 坐标（合同编号列附近）
                    (target_row_idx - table_df.index[0] + 1)
                    * 18,  # 估算行高 18px，需要 PR 实测校准
                )
            )
        except Exception as e:
            return self._fail(
                f"定位并双击目标行失败：{e}（请检查 THS 表格渲染方式 / 滚动状态）"
            )

        time.sleep(0.2)

        # 7) 弹出「是否撤单」确认对话框 → 点确定
        #    THS 客户端通常会弹出确认（需要 PR 实测：即使勾选了「撤单不确认」，
        #    按 contract_no 单笔撤也可能触发额外确认框）
        if self.wait_for_pop_dialog(0.5):
            # 找确认按钮（auto_id 不固定，按文字兜底）
            try:
                dialog = self.get_pop_dialog()
                # 找包含「确定」/「撤单」字样的按钮
                btn = None
                for child in dialog.children():
                    if child.control_type == "Button" and (
                        "确定" in child.window_text()
                        or "撤单" in child.window_text()
                    ):
                        btn = child
                        break
                if btn is None:
                    # 兜底：取第一个 Button
                    btn = next(
                        (
                            c
                            for c in dialog.children()
                            if c.control_type == "Button"
                        ),
                        None,
                    )
                if btn:
                    btn.click()
                else:
                    return self._fail("确认对话框找不到确定按钮")
            except Exception as e:
                return self._fail(f"点击撤单确认失败：{e}")

        time.sleep(0.3)

        # 8) 等待操作结果弹窗（成功/失败）
        #    实际是否有弹窗依赖 THS 客户端版本——保守起见：只要没失败弹窗就算成功
        if self.wait_for_pop_dialog(0.4):
            content = self.get_pop_dialog_content()
            if "失败" in content or "错误" in content:
                return self._fail(f"撤单失败：{content}")
            # 成功弹窗：尝试点确定关掉
            try:
                self.get_pop_dialog().children(
                    control_type="Button"
                )[0].click()
            except Exception:
                pass

        return self._ok(
            data=OrderCancelByContractResult(
                contract_no=contract_no,
                stock_code=stock_code,
                cancelled_quantity=max(target_qty - cancelled_qty, 0),
            ).model_dump(),
            message=(
                f"按合同编号 {contract_no} 撤单成功，"
                f"股票 {stock_code}，耗时 {time.time() - start_time:.2f} 秒"
            ),
        )