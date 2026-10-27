# amazon-voc-pay

> WorkBuddy Skill — `amazon-voc-pay`

## 简介

按次付费的 Amazon 评论 VOC 洞察（支付宝 AI 按量付费，1.99 元/次，无需注册账号）。 给一个 ASIN 和站点，自动采集最新评论并生成 VOC 报告：差评痛点、购买动因、用户画像、 使用场景、改进机会与 Listing 建议，附可分享的在线报告链接。 Use when the user wants a one-off Amazon review analysis / voice of customer report for an ASIN and prefers pay-pe

## 安装

```bash
git clone https://github.com/funewa/amazon-voc-pay.git
cp -r amazon-voc-pay ~/.workbuddy/skills/amazon-voc-pay
```

## 使用

在 WorkBuddy 中直接描述你的需求，Agent 会依据 `SKILL.md` 的 `description` 自动匹配本技能。详见 `SKILL.md`。

## 目录结构

```
├── SKILL.md      # 技能定义（frontmatter + 说明）
├── scripts/
├── references/
├── agents/
└── README.md
```

---

Published from the `user`-level WorkBuddy skill library.
