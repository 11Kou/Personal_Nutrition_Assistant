---
doc_type: fitness_rehab_source_index
language: zh-CN
intended_use: rag_metadata_and_query_routing
doc_domain: fitness_rehab
source_note: 本索引用于健身、身体活动、运动伤病和康复建议的 RAG 路由；不用于诊断、治疗或替代医生/物理治疗师建议。
sources:
  - CDC Adult Activity: An Overview
  - HHS Physical Activity Guidelines for Americans
  - WHO Guidelines on Physical Activity and Sedentary Behaviour
  - AAOS OrthoInfo
  - NHS Exercise
  - NHS Sprains and Strains
---

# 运动健身与伤病资料索引

本索引用于把用户画像中的 `injuries`、`training_conditions`、`medical_conditions` 与适合检索的运动/康复小文档关联起来。它不是动作诊断工具，不根据症状判断疾病或损伤类型。

## physical_activity_general

- 中文名：成年人身体活动通用指南
- 适用问题：每周运动多久、力量训练频率、久坐、慢病人群如何开始运动
- 主要来源：CDC、HHS、WHO
- 主要标签：aerobic_training, strength_training, sedentary_behavior, chronic_condition_caution
- 检索关键词：有氧运动、力量训练、每周 150 分钟、久坐、慢病、循序渐进

## injury_self_care_triage

- 中文名：扭伤、拉伤与运动损伤分流
- 适用问题：受伤后能不能练、什么时候停训、什么时候就医
- 主要来源：NHS
- 主要标签：pain_stop_rule, urgent_care, sprain, strain, swelling, bruising
- 检索关键词：扭伤、拉伤、疼痛、肿胀、PRICE、停止运动、就医

## knee_rehab

- 中文名：膝关节康复与训练注意事项
- 适用问题：膝痛、膝伤、下肢训练替代、低冲击运动
- 主要来源：AAOS OrthoInfo
- 主要标签：knee, low_impact, rehab, avoid_pain
- 检索关键词：膝伤、膝痛、下肢训练、低冲击、康复、疼痛停止

## shoulder_rehab

- 中文名：肩袖与肩关节训练注意事项
- 适用问题：肩痛、肩伤、推举替代、肩关节活动度
- 主要来源：AAOS OrthoInfo
- 主要标签：shoulder, rotator_cuff, range_of_motion, avoid_pain
- 检索关键词：肩袖、肩痛、肩伤、推举、活动度、康复

## spine_rehab

- 中文名：脊柱、腰背训练注意事项
- 适用问题：腰痛、背痛、核心训练、动作选择
- 主要来源：AAOS OrthoInfo、NHS
- 主要标签：spine, back, core_stability, avoid_pain
- 检索关键词：腰痛、背痛、核心、脊柱、鸟狗、疼痛停止

## foot_ankle_rehab

- 中文名：足踝康复与训练注意事项
- 适用问题：踝伤、足踝扭伤、跑步恢复、小腿力量
- 主要来源：AAOS OrthoInfo、NHS
- 主要标签：ankle, foot, sprain, low_impact, rehab
- 检索关键词：踝伤、脚踝、扭伤、小腿、低冲击、恢复跑步

