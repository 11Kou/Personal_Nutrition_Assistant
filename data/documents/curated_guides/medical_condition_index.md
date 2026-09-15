---
doc_type: medical_condition_index
language: zh-CN
intended_use: rag_metadata_and_query_routing
source_group: 国家卫生健康委成人食养指南
source_authority: 国家卫生健康委办公厅
source_note: 原始 PDF 不纳入 Git；项目引用优先使用 source_title 和 source_authority，本地核对时再使用 source_local_pdf。
conditions:
  - hypertension
  - hyperlipidemia
  - ckd
  - diabetes
  - obesity
  - gout
---

# 常见疾病与健康状况索引

本索引用于项目中的 `medical_conditions` 字段标准化、查询改写、检索过滤和安全提示。它不是诊断工具，不根据症状判断用户是否患病。

## hypertension

- 中文名：高血压
- 别名：血压高、成人高血压、hypertension
- 主要风险标签：limit_sodium, potassium_caution_if_ckd, weight_management, alcohol_caution
- 检索关键词：减钠增钾、清淡饮食、血压监测、健康体重、限酒
- 回答边界：涉及用药调整、血压分级诊断、急性症状时建议就医。

## hyperlipidemia

- 中文名：高脂血症
- 别名：血脂异常、血脂高、hyperlipidemia, dyslipidemia
- 主要风险标签：limit_saturated_fat, limit_trans_fat, limit_cholesterol, increase_fiber, weight_management
- 检索关键词：少油烹饪、饱和脂肪、反式脂肪、胆固醇、膳食纤维
- 回答边界：涉及降脂药调整、心血管疾病风险判断时建议就医。

## ckd

- 中文名：慢性肾脏病
- 别名：慢性肾病、肾功能不全、CKD, chronic kidney disease
- 主要风险标签：protein_caution, limit_sodium, phosphorus_caution, potassium_caution, fluid_caution
- 检索关键词：分期选配、低蛋白、限磷控钾、量出为入、肾病营养
- 回答边界：不得直接推荐高蛋白饮食；涉及蛋白、钾、磷、饮水量时提示按分期和化验指标咨询医生或临床营养师。

## diabetes

- 中文名：糖尿病
- 别名：2型糖尿病、血糖高、diabetes, type 2 diabetes
- 主要风险标签：carb_control, low_gi, limit_added_sugar, regular_meals, hypoglycemia_caution
- 检索关键词：主食定量、低GI、餐后血糖、规律进餐、合理加餐
- 回答边界：涉及药物、胰岛素、低血糖、妊娠糖尿病或1型糖尿病时建议就医。

## obesity

- 中文名：肥胖
- 别名：超重、减重、obesity, overweight
- 主要风险标签：calorie_deficit, avoid_extreme_diet, weight_management, exercise_progression
- 检索关键词：控制总能量、限能量平衡膳食、安全减重、饮食行为、运动消耗
- 回答边界：不推荐极端节食；合并慢病、孕期、哺乳期、老人减重时建议专业指导。

## gout

- 中文名：高尿酸血症与痛风
- 别名：痛风、高尿酸、尿酸高、gout, hyperuricemia
- 主要风险标签：low_purine, avoid_high_purine, limit_fructose, alcohol_caution, hydration_if_kidney_ok
- 检索关键词：限制嘌呤、动物内脏、果糖、饮水、限酒、急性痛风
- 回答边界：急性痛风发作期、肾功能不全、药物控制不佳时建议就医；饮水建议需结合心肾功能。
