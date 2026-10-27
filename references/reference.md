# Amazon VOC 按次付费 接口契约

服务地址：`https://voc.funewa.com`。协议：支付宝「AI 按量付费」A2M（HTTP 402 / `Payment-Needed` / `Payment-Proof`）。
所有端点公开、免账号，按来源 IP 限流。

## GET /api/v1/pay/skus

价目表。`data.skus[]`：`sku`、`goodsName`、`amountCny`、`credits`（内部记账）、`pages`（采集页数）。

## GET|POST /api/v1/pay/voc

参数（GET query 或 POST JSON）：

| 字段 | 说明 |
|---|---|
| `asin` | 必填，10 位字母数字 |
| `site` | `US`/`UK`/`DE`/`FR`/`IT`/`ES`/`CA`/`JP`（也接受 `amz_us` 等），缺省 US |
| `language` | `zh`（缺省，报告中文）/ `en` |

### 无 `Payment-Proof` → 402

- 头 `Payment-Needed`：Base64URL 编码的账单 JSON（`protocol.out_trade_no/amount/currency/resource_id/pay_before/seller_signature/...`，`method.goods_name/service_id/...`）。
- 体：`{"error":"Payment Needed","message":"需支付 1.99 CNY …","resourceId":"voc:<ASIN>:<site>:<lang>","code":"ARI_PAYMENT_NEEDED","data":{outTradeNo, amount, currency, goodsName, payBefore, howTo}}`。
- 凭证被拒时同样返回 402 + 新账单，并多一个 `reason` 字段说明原因（凭证无效 / 金额不符 / 资源不符 / 已兑付 / 账单过期）。

`resource_id = voc:<ASIN>:<amz_site>:<language>`：付款绑定到这组参数，换 ASIN、站点或语言都要重新付款。账单 15 分钟内有效。

### 带 `Payment-Proof` → 200

服务端验付（`alipay.aipay.agent.payment.verify`，核对 active / 金额 / 账单号 / 资源 / 交易号唯一）后开始交付。响应头 `Payment-Validation`（Base64URL JSON：`validated`、`trade_no`、`out_trade_no`、`resource_id`）。

**交付完成**（45 秒内完成时直接返回）：

```json
{
  "success": true, "code": "OK",
  "resourceId": "voc:B0CX18LHWS:amz_us:zh-CN", "content": "<报告 Markdown 全文>",
  "tradeNo": "2026…", "outTradeNo": "A2M…",
  "data": {
    "asin": "...", "site": "amz_us", "language": "zh-CN", "totalReviews": 131,
    "collection": {"taskId": "...", "status": "done", "result": {...}},
    "report": {"reportId": 84, "creditsUsed": 25, "content": "...", "reportUrl": "https://ari.funewa.com/zh/share/<token>"},
    "collectionFailed": false, "partial": false,
    "message": "VOC 报告已生成。",
    "next": "绑定 ARI 账号可保留这份报告、开启每周自动采集并与下一份报告做环比：https://ari.funewa.com/zh/register?source=a2m"
  }
}
```

- `collectionFailed=true` + `notice`：本次最新评论采集失败，报告基于评论库已有评论生成。
- `partial=true`：可用评论不足 10 条，未生成报告（`content` 为说明文字）；`needsReview=true` 供客服退款。

**已付款、报告生成中**（超过 45 秒未完成）：

```json
{"success": true, "status": "processing", "resourceId": "...", "content": "已验付，VOC 报告正在生成…",
 "tradeNo": "...", "outTradeNo": "...", "resultUrl": "https://voc.funewa.com/api/v1/pay/result/<outTradeNo>?tradeNo=<tradeNo>",
 "retryAfterSeconds": 10}
```

按 `resultUrl` 每 10 秒取一次，或携带同一 `Payment-Proof` 重试本请求（幂等，免费）。

### 错误

| HTTP | code | 含义 / 处理 |
|---|---|---|
| 402 | `ARI_PAYMENT_NEEDED` | 需付款或凭证被拒（看 `reason`） |
| 422 | `ARI_VALIDATION_ERROR` | ASIN / 站点 / 语言不合法 |
| 404 | `ARI_NOT_FOUND` | 未知 SKU，或域名不对（只在 voc.funewa.com 响应） |
| 429 | `ARI_RATE_LIMITED` | 限流，稍后再试 |
| 500 | `ARI_PAY_DELIVERY_FAILED` | 已付款但交付失败；消息含 `tradeNo`，交客服退款，**不要重新支付** |
| 502 | `ARI_UPSTREAM_ERROR` | 支付宝验付暂不可用；稍后用同一凭证重试 |
| 503 | `ARI_PAY_UNAVAILABLE` | 服务未开放 |

## GET /api/v1/pay/result/{outTradeNo}?tradeNo=…

免凭证取结果：`tradeNo`（支付宝交易号）即凭据。返回与上面 200 相同的三种形态；账单号与交易号不匹配返回 404。

## 幂等与安全

- 同一 `trade_no` 只兑付一次；同凭证重试永远返回同一结果，不会二次收费。
- 一张账单只能被一笔支付兑付；支付金额、资源必须与账单完全一致。
- 服务端不接触买家支付宝账号；买家身份只有会话标识，报告按会话归到匿名影子账号，不会出现在任何邮件或推送里。
