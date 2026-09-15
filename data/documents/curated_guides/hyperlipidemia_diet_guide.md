---
doc_type: curated_medical_guide
condition_id: hyperlipidemia
condition_name: 成人高脂血症
language: zh-CN
source_title: 成人高脂血症食养指南（2023年版）
source_authority: 国家卫生健康委办公厅
source_local_pdf: documentsource/成人高脂血症食养指南（2023年版）.pdf
source_note: 原始 PDF 不纳入 Git；本地路径仅用于开发时核对原文，RAG 对外引用使用 source_title 和 source_authority。
risk_tags:
  - limit_saturated_fat
  - limit_trans_fat
  - limit_cholesterol
  - increase_fiber
  - weight_management
topics:
  - diet
  - lipid_control
  - lifestyle
---

# 成人高脂血症食养小文档

## 适用边界

适用于成人高脂血症或血脂异常人群的日常饮食和生活方式建议。不能替代血脂诊断、心血管风险评估或降脂药物管理。

## 核心原则

- 吃动平衡，保持健康体重。
- 调控脂肪，少油烹饪。
- 食物多样，保证蛋白质和膳食纤维摄入。
- 少盐控糖，戒烟限酒。
- 根据个体情况调整膳食，不做一刀切。

## 饮食建议

- 总脂肪摄入以占总能量 20%-25% 为宜；高甘油三酯血症者更应减少脂肪总量。
- 每日烹调油不超过 25g。
- 饱和脂肪应少于总能量 10%；高胆固醇血症者应进一步降低。
- 胆固醇摄入一般少于每日 300mg，高胆固醇血症者少于每日 200mg。
- 减少或避免反式脂肪酸，少吃含部分氢化植物油的加工食品。
- 多选择蒸、煮等少油烹饪方式，减少油炸、油煎。
- 主食适当减少精白米面，增加全谷物、杂豆和蔬菜等富含膳食纤维的食物。
- 新鲜蔬菜推荐每日约 500g，水果约 200-350g。

## 运动和生活方式

- 超重或肥胖者可通过膳食结构调整和运动减重。
- 一般建议每周 5-7 次中等及以上强度身体活动，每次约 30 分钟。
- 稳定性动脉粥样硬化性心血管疾病患者运动前应评估安全性。

## RAG 使用提示

- 当用户画像包含 `hyperlipidemia` 时，过滤或降低高油、高饱和脂肪、高胆固醇食物建议的优先级。
- 回答食物选择时优先提示烹饪方式和脂肪类型，而不只看总热量。
- 涉及药物、胸痛、冠心病、脑卒中风险时建议就医。
