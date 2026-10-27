#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Amazon VOC 按次付费（支付宝 AI 按量付费 / HTTP 402）命令行。

仅标准库。付款本身由支付宝 Agent 支付能力完成，本脚本只负责：
  price   价目表（免费）
  quote   取 402 账单（不扣钱），输出 Payment-Needed 头原值供支付能力使用
  retry   携带 Payment-Proof 取报告；报告生成中自动轮询
  result  用账单号 + 支付宝交易号取结果（免凭证，可反复调用）

所有输出为 JSON，一行一个对象，便于 Agent 读取。退出码：0 正常（含 402 账单）、1 错误。
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.0.0"
CHANNEL = "skillhub-pay"
PROD_BASE = "https://voc.funewa.com"
TIMEOUT_SEC = 90
POLL_SEC = 10
DEFAULT_WAIT_SEC = 300
SITES = ("US", "UK", "DE", "FR", "IT", "ES", "CA", "JP")

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def base_url():
    """基址。VOC_PAY_BASE_URL 覆盖必须同时设置 VOC_PAY_ALLOW_CUSTOM_BASE=1，
    防止一条被注入的 shell 命令把支付凭证发到第三方主机。"""
    custom = os.environ.get("VOC_PAY_BASE_URL", "").strip().rstrip("/")
    if custom and os.environ.get("VOC_PAY_ALLOW_CUSTOM_BASE") == "1":
        return custom
    return PROD_BASE


def user_agent():
    return "amazon-voc-pay/%s ch/%s python/%d.%d" % (VERSION, CHANNEL, sys.version_info[0], sys.version_info[1])


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False))


def fail(code, message, hint=None, **extra):
    out = {"success": False, "code": code, "message": message}
    if hint:
        out["hint"] = hint
    out.update(extra)
    emit(out)
    sys.exit(1)


def resource_url(asin, site, language):
    q = urllib.parse.urlencode({"asin": asin.upper().strip(), "site": site.upper(), "language": language})
    return "%s/api/v1/pay/voc?%s" % (base_url(), q)


def http(url, headers=None):
    """返回 (status, headers, body_json_or_None, raw_text)。"""
    h = {"Accept": "application/json", "User-Agent": user_agent()}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, dict(resp.headers), _json(raw), raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers), _json(raw), raw
    except Exception as exc:  # 网络层
        fail("NETWORK_ERROR", str(exc), "检查网络后重试；已付款的请求重试是免费的，不要重新支付。")


def _json(raw):
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def header(headers, name):
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return ""


def decode_payment_needed(value):
    s = value.strip()
    s += "=" * (-len(s) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(s))
    except Exception:
        return None


def check_asin(asin):
    a = asin.upper().strip()
    if len(a) != 10 or not a.isalnum():
        fail("INVALID_ASIN", "ASIN 必须是 10 位字母数字（商品链接 /dp/ 后面那段）")
    return a


def cmd_price(_args):
    status, _h, body, raw = http(base_url() + "/api/v1/pay/skus")
    if status != 200 or not body:
        fail("PRICE_UNAVAILABLE", "价目表暂不可用（HTTP %d）" % status, "服务可能未开放，稍后再试", raw=raw[:300])
    data = body.get("data") or {}
    skus = data.get("skus") or []
    voc = next((s for s in skus if s.get("sku") == "voc"), None)
    emit({
        "success": True,
        "skus": skus,
        "summary": ("VOC 报告 %s 元/次：采集最新 %s 页评论 + 完整 VOC 报告 + 在线分享链接，约 1–3 分钟"
                    % (voc.get("amountCny"), voc.get("pages"))) if voc else "",
        "paymentMethod": "支付宝 AI 按量付费（HTTP 402 / Payment-Needed），付款前会再次展示金额",
    })


def cmd_quote(args):
    asin = check_asin(args.asin)
    url = resource_url(asin, args.site, args.language)
    status, h, body, raw = http(url)
    if status == 402:
        pn_raw = header(h, "Payment-Needed")
        pn = decode_payment_needed(pn_raw) or {}
        proto, meth = pn.get("protocol", {}), pn.get("method", {})
        emit({
            "success": True,
            "status": "payment_needed",
            "url": url,
            "amount": proto.get("amount"), "currency": proto.get("currency"),
            "goodsName": meth.get("goods_name"),
            "outTradeNo": proto.get("out_trade_no"), "resourceId": proto.get("resource_id"),
            "payBefore": proto.get("pay_before"),
            "paymentNeeded": pn_raw,
            "reason": (body or {}).get("reason"),
            "howTo": ("把 paymentNeeded 交给支付宝 Agent 支付能力完成付款（或对 url 发起请求由其自动处理 402），"
                      "拿到 Payment-Proof 后运行：retry %s --site %s --language %s --proof <Payment-Proof>"
                      % (asin, args.site.upper(), args.language)),
            "noPaymentCapability": ("当前客户端若没有支付宝 Agent 支付能力：请用户运行 "
                                    "npx -y @alipay/agent-payment@latest install-experience 安装官方付款能力后重试；"
                                    "本服务没有网页付款入口，不要编造购买页面。说明页 https://voc.funewa.com"),
        })
        return
    if status == 200 and body:
        emit({"success": True, "status": "delivered", "note": "该请求无需付款即返回了结果", "data": body.get("data")})
        return
    fail((body or {}).get("code") or "HTTP_%d" % status, (body or {}).get("message") or raw[:300])


def render_outcome(status, h, body, raw, asin, site, language):
    """把服务端 200/500/402 统一成一个结果对象；返回 (obj, done)。"""
    if status == 200 and body:
        data = body.get("data") or {}
        st = body.get("status") or data.get("status") or "delivered"
        if st == "processing":
            return {
                "success": True, "status": "processing",
                "outTradeNo": body.get("outTradeNo"), "tradeNo": body.get("tradeNo"),
                "resultUrl": body.get("resultUrl"), "retryAfterSeconds": body.get("retryAfterSeconds", POLL_SEC),
                "message": body.get("content"),
            }, False
        report = data.get("report") or {}
        return {
            "success": True, "status": "delivered",
            "asin": data.get("asin", asin), "site": data.get("site", site), "language": data.get("language", language),
            "outTradeNo": body.get("outTradeNo"), "tradeNo": body.get("tradeNo"),
            "reportId": report.get("reportId"), "reportUrl": report.get("reportUrl"),
            "content": body.get("content") or report.get("content"),
            "totalReviews": data.get("totalReviews"),
            "collectionFailed": bool(data.get("collectionFailed")), "notice": data.get("notice"),
            "partial": bool(data.get("partial")), "message": data.get("message"),
            "next": data.get("next"),
        }, True
    if status == 402:
        pn_raw = header(h, "Payment-Needed")
        return {
            "success": False, "status": "payment_needed", "code": "ARI_PAYMENT_NEEDED",
            "reason": (body or {}).get("reason") or "凭证未被接受",
            "paymentNeeded": pn_raw,
            "message": "服务端未接受该支付凭证，返回了新账单。先把 reason 告诉用户，确认后才重新付款。",
        }, True
    code = (body or {}).get("code") or "HTTP_%d" % status
    return {
        "success": False, "status": "failed", "code": code,
        "message": (body or {}).get("message") or raw[:300],
        "hint": {
            "ARI_PAY_DELIVERY_FAILED": "已付款但交付失败：把消息里的支付宝交易号给用户用于退款；不要重新支付。",
            "ARI_NOT_FOUND": "账单号与支付宝交易号不匹配（或 SKU/域名不对），核对后重试；不要重新支付。",
            "ARI_VALIDATION_ERROR": "ASIN / 站点 / 语言参数不合法，修正后重试。",
            "ARI_PAY_UNAVAILABLE": "服务暂未开放，稍后再试。",
        }.get(code, "稍后用同一 Payment-Proof 重试（免费）。"),
    }, True


def poll_result(out_trade_no, trade_no, wait_sec, asin="", site="", language=""):
    url = "%s/api/v1/pay/result/%s?%s" % (base_url(), urllib.parse.quote(out_trade_no),
                                           urllib.parse.urlencode({"tradeNo": trade_no}))
    deadline = time.time() + wait_sec
    last = None
    while True:
        status, h, body, raw = http(url)
        last, done = render_outcome(status, h, body, raw, asin, site, language)
        if done or time.time() >= deadline:
            if not done:
                last["message"] = ("报告仍在生成（已等待 %d 秒）。稍后运行 result %s %s 再取，不要重新支付。"
                                   % (wait_sec, out_trade_no, trade_no))
                last["resultCommand"] = "result %s %s" % (out_trade_no, trade_no)
            return last
        time.sleep(POLL_SEC)


def cmd_retry(args):
    asin = check_asin(args.asin)
    proof = args.proof.strip()
    if not proof:
        fail("MISSING_PROOF", "--proof 需要 Payment-Proof 头原值")
    url = resource_url(asin, args.site, args.language)
    status, h, body, raw = http(url, {"Payment-Proof": proof})
    out, done = render_outcome(status, h, body, raw, asin, args.site.upper(), args.language)
    if not done and out.get("outTradeNo") and out.get("tradeNo"):
        out = poll_result(out["outTradeNo"], out["tradeNo"], args.wait, asin, args.site.upper(), args.language)
    emit(out)
    if not out.get("success"):
        sys.exit(1)


def cmd_result(args):
    out = poll_result(args.out_trade_no.strip(), args.trade_no.strip(), args.wait)
    emit(out)
    if not out.get("success"):
        sys.exit(1)


def main(argv=None):
    p = argparse.ArgumentParser(description="Amazon VOC 按次付费（支付宝 AI 按量付费）")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("price", help="价目表（免费）").set_defaults(func=cmd_price)

    def common(sp):
        sp.add_argument("asin")
        sp.add_argument("--site", default="US", choices=SITES, type=str.upper, help="站点，缺省 US")
        sp.add_argument("--language", default="zh", help="报告语言 zh / en，缺省 zh")

    q = sub.add_parser("quote", help="取 402 账单（不扣钱）")
    common(q)
    q.set_defaults(func=cmd_quote)
    r = sub.add_parser("retry", help="携带 Payment-Proof 取报告")
    common(r)
    r.add_argument("--proof", required=True, help="Payment-Proof 头原值")
    r.add_argument("--wait", type=int, default=DEFAULT_WAIT_SEC, help="报告生成中的最长等待秒数")
    r.set_defaults(func=cmd_retry)
    s = sub.add_parser("result", help="按账单号 + 支付宝交易号取结果")
    s.add_argument("out_trade_no")
    s.add_argument("trade_no")
    s.add_argument("--wait", type=int, default=DEFAULT_WAIT_SEC)
    s.set_defaults(func=cmd_result)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
