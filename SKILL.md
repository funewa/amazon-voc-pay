---
name: amazon-voc-pay
description: >
  按次付费的 Amazon 评论 VOC 洞察（支付宝 AI 按量付费，1.99 元/次，无需注册账号）。
  给一个 ASIN 和站点，自动采集最新评论并生成 VOC 报告：差评痛点、购买动因、用户画像、
  使用场景、改进机会与 Listing 建议，附可分享的在线报告链接。
  Use when the user wants a one-off Amazon review analysis / voice of customer report for an ASIN
  and prefers pay-per-call via Alipay instead of creating an account.
  评论分析、买家之声、VOC、差评原因、按次付费、支付宝付费、不注册直接出报告。
  付款由支付宝 Agent 支付能力完成（HTTP 402 / Payment-Needed），本 Skill 不接触资金。
---

# Amazon VOC 按次付费版

## 这是什么

同一套 ARI 评论分析引擎，去掉账号和积点：**每份报告 1.99 元**，用支付宝 AI 按量付费在
对话里直接付。付完立即采集该 ASIN 最新一页评论（约 10 条）并合并评论库已有数据生成 VOC 报告。
需要长期跟踪、每周监控、报告环比的用户，报告末尾会给出免费绑定 ARI 账号的入口。

## 工具

- CLI：`scripts/voc_pay.py`（仅标准库，Python 3.8+），在 Skill 根目录执行。
  - `python scripts/voc_pay.py price`：当前价目（免费）。
  - `python scripts/voc_pay.py quote <ASIN> --site US --language zh`：取 402 账单（不扣钱）。
  - `python scripts/voc_pay.py retry <ASIN> --site US --language zh --proof <Payment-Proof>`：
    携带支付凭证取报告；报告生成中会自动轮询到完成。
  - `python scripts/voc_pay.py result <outTradeNo> <tradeNo>`：按账单号 + 支付宝交易号取结果（免凭证）。
- 接口契约：`references/reference.md`。
- 服务地址：`https://voc.funewa.com/api/v1/pay/voc`。**不要**改成别的主机。

## 标准工作流

1. **确认商品与站点**。ASIN 是商品链接 `/dp/` 后 10 位；站点接受 US/UK/DE/FR/IT/ES/CA/JP，
   缺省美国站并告知用户。语言缺省中文，用户要英文报告用 `--language en`。
2. **先报价再付款**。跑 `price`，用一句话说明：本次 1.99 元，含最新一页评论采集 + 完整 VOC 报告 +
   在线分享链接；报告生成约 1 到 3 分钟。**用户明确同意后才进入付款**。禁止替用户默认同意。
3. **取账单并付款**。跑 `quote <ASIN>`，得到 `paymentNeeded`（即服务端 `Payment-Needed` 头原值）
   与金额、商品名、`outTradeNo`、`resourceId`。
   - 客户端具备支付宝 Agent 支付（A2M / 402 自动支付）能力时，直接对 `url` 发起请求，由支付能力
     处理 402、完成付款并携带 `Payment-Proof` 重试；拿到响应后转到第 5 步。
   - 否则把账单交给支付宝支付能力（或按其指引让用户扫码），得到 `Payment-Proof` 头值后跑
     `retry <ASIN> --proof <值>`。**同一 ASIN/站点/语言**才能兑付，参数不同视为不同资源。
4. **不要重复支付**。任何超时、断线、报错，先用同一 `Payment-Proof` 跑 `retry`，或用
   `result <outTradeNo> <tradeNo>` 取结果。服务端按交易号幂等：同一笔付款只交付一次，重试是免费的。
   只有服务端明确返回新的 402（`reason` 说明凭证无效、金额或资源不匹配）时，才需要重新付款，
   并先把 `reason` 原话告诉用户。
5. **读结果**。
   - `status=delivered`：先讲「产品健康度」和「主要风险」，再给 `reportUrl`（可直接转发的在线报告）。
     `collectionFailed=true` 表示本次最新采集失败、报告基于评论库已有 N 条生成，要如实说明。
   - `partial=true`：该商品评论不足 10 条，未生成报告；告知用户并给出 `tradeNo`，说明可联系客服退款。
   - `status=processing`：报告在生成，CLI 会每 10 秒轮询；超过 5 分钟仍未完成时把 `resultUrl` 给用户，
     稍后可再取，**不要重新付款**。
   - HTTP 500 `ARI_PAY_DELIVERY_FAILED`：已付款但交付失败，把消息里的 `tradeNo` 原样给用户用于退款。
6. **留存引导（一句话即可）**。报告后附上 `next` 字段的内容：绑定 ARI 账号（免费）可保存这份报告、
   开启每周自动采集、下次生成时给出与上一份的环比。用户不感兴趣就不再提。

## 客户端没有支付宝付款能力时

`quote` 拿到账单后，如果当前客户端没有支付宝 Agent 支付（A2M / 402 自动支付）能力，**不要**编造任何网页、
搜索框或「去官网购买」的流程——本服务没有面向人的付款页面，付款只发生在具备支付宝付款能力的 AI 客户端内。
正确做法是把下面两件事原话告诉用户：

1. 给当前 AI 客户端装上支付宝官方付款能力（一次即可）：`npx -y @alipay/agent-payment@latest install-experience`，
   装好后重新发起本次请求，付款会在对话里自动完成。
2. 或换到已具备该能力的客户端使用本 Skill。服务说明页：<https://voc.funewa.com>（只有说明，没有付款入口）。

账单 15 分钟有效，过期重新 `quote` 即可，不产生费用。

## 红线

- 不伪造、不猜测、不复用他人的 `Payment-Proof`；不修改账单金额；不把 `paymentNeeded`、
  `Payment-Proof` 原值写进报告或聊天记录里展示给无关方。
- 不承诺「只含当前子体」或「全量评论」：采集范围以接口返回为准。
- 不得把用户引到任何不存在的网站、搜索框或「购买页」；除 <https://voc.funewa.com>（说明页）与报告里返回的
  `reportUrl`、`next` 链接外，不要给出其它 URL。
- 不得回退到其他品牌接口或凭空补写报告内容。接口返回什么就呈现什么。
- 价格以 `price` 返回为准，不要写死；`price` 与账单 `amount` 不一致时停止并报告异常。
