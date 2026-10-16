# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/template.c
# Historical Aerospace sources:
#   btech/aero.bomb.c
#   btech/template.c

"""Part names and fixed-point weights from template.c (complex repairs enabled).
Table indices intentionally preserve source mismatches and missing entries.
Copyright (c) 1996 Markus Stenberg; 1998-2002 Thomas Wouters;
2000-2002 Cord Awtry. All rights reserved.
"""

INTERNALS = (
    "ShoulderOrHip",
    "UpperActuator",
    "LowerActuator",
    "HandOrFootActuator",
    "LifeSupport",
    "Sensors",
    "Cockpit",
    "Engine",
    "Gyro",
    "HeatSink",
    "JumpJet",
    "CASE",
    "FerroFibrous",
    "EndoSteel",
    "TripleStrengthMyomer",
    "TargetingComputer",
    "Masc",
    "C3Master",
    "C3Slave",
    "BeagleProbe",
    "ArtemisIV",
    "Ecm",
    "Axe",
    "Sword",
    "Mace",
    "Claw",
    "DSAeroDoor",
    "DSMechDoor",
    "Fuel_Tank",
    "TAG",
    "DSVehicleDoor",
    "DSCargoDoor",
    "LAM_Equipment",
    "CASE-II",
    "StealthArmor",
    "NullSig_Device",
    "C3i",
    "AngelEcm",
    "HvyFerroFibrous",
    "LtFerroFibrous",
    "BloodhoundProbe",
    "PurifierArmor",
    "KageStealthUnit",
    "AchileusStealthUnit",
    "InfiltratorStealthUnit",
    "InfiltratorIIStealthUnit",
    "SuperCharger",
    "Dual_Saw",
    "Light_BAP",
    "SplitCrit_Left",
    "SplitCrit_Right",
    "Hardpoint",
)

CARGO = (
    "Ammo_LBX2",
    "Ammo_LBX5_LBX",
    "Ammo_LBX10_LBX",
    "Ammo_LBX20_LBX",
    "Ammo_LRM",
    "Ammo_SRM",
    "Ammo_SSRM",
    "Ammo_LRM_NARC",
    "Ammo_SRM_NARC",
    "Ammo_SSRM_NARC",
    "Ammo_LRM_Artemis",
    "Ammo_SRM_Artemis",
    "Ammo_SSRM_Artemis",
    "Petroleum",
    "Phosphorus",
    "Hydrogen",
    "Gold",
    "Natural_Extracts",
    "Marijuana",
    "Sulfur",
    "Sodium",
    "Plutonium",
    "Ore",
    "Steel",
    "Plastics",
    "Medical_Supplies",
    "Computers",
    "Explosives",
    "ES_Internal",
    "FF_Armor",
    "XL_Engine",
    "Double_HeatSink",
    "ICE_Engine",
    "Electric",
    "Internal",
    "Armor",
    "Actuator",
    "Aero_Fuel",
    "DS_Fuel",
    "VTOL_Fuel",
    "Ammo_LRM_Swarm",
    "Ammo_LRM_Swarm1",
    "Ammo_SRM_Inferno",
    "XXL_Engine",
    "Compact_Engine",
    "HD_Armor",
    "RE_Internals",
    "CO_Internals",
    "Ammo_MRM",
    "Light_Engine",
    "CASE-II",
    "STH_Armor",
    "NullSigSys",
    "Silicon",
    "HVY_FF_Armor",
    "LT_FF_Armor",
    "Ammo_iNARC_Explosive",
    "Ammo_iNARC_Haywire",
    "Ammo_iNARC_ECM",
    "Ammo_iNARC_Nemesis",
    "Ammo_AC2_Pierce",
    "Ammo_AC5_Pierce",
    "Ammo_AC10_Pierce",
    "Ammo_AC20_Pierce",
    "Ammo_LAC2_Pierce",
    "Ammo_LAC5_Pierce",
    "Ammo_AC2_Flechette",
    "Ammo_AC5_Flechette",
    "Ammo_AC10_Flechette",
    "Ammo_AC20_Flechette",
    "Ammo_LAC2_Flechette",
    "Ammo_LAC5_Flechette",
    "Ammo_AC2_Incendiary",
    "Ammo_AC5_Incendiary",
    "Ammo_AC10_Incendiary",
    "Ammo_AC20_Incendiary",
    "Ammo_LAC2_Incendiary",
    "Ammo_LAC5_Incendiary",
    "Ammo_AC2_Precision",
    "Ammo_AC5_Precision",
    "Ammo_AC10_Precision",
    "Ammo_AC20_Precision",
    "Ammo_LAC2_Precision",
    "Ammo_LAC5_Precision",
    "Ammo_LR_DFM",
    "Ammo_SR_DFM",
    "Ammo_SLRM",
    "Ammo_ELRM",
    "BSuit_Sensor",
    "BSuit_LifeSupport",
    "BSuit_Electronic",
    "Oil",
    "Water",
    "Earth",
    "Oxygen",
    "Nitrogen",
    "Nickel",
    "Steel",
    "Iron",
    "Brass",
    "Platinum",
    "Copper",
    "Aluminum",
    "Consumer_Good",
    "Machinery",
    "Slaves",
    "Timbiqui_Dark",
    "Cocaine",
    "Heroine",
    "Marble",
    "Glass",
    "Diamond",
    "Coal",
    "Food",
    "Zinc",
    "Fabric",
    "Clothing",
    "Wood",
    "Pulp",
    "Lumber",
    "Rubber",
    "Seeds",
    "Fertilizer",
    "Salt",
    "Lithium",
    "Helium",
    "Larium",
    "Uranium",
    "Iridium",
    "Titanium",
    "Concrete",
    "FerroCrete",
    "Building_Supplies",
    "Kevlar",
    "Waste",
    "Livestock",
    "Paper",
    "XL_Gyro",
    "HeavyDuty_Gyro",
    "Compact_Gyro",
    "Compact_HeatSink",
    "Ammo_LRM_Stinger",
    "Ammo_AC2_Caseless",
    "Ammo_AC5_Caseless",
    "Ammo_AC10_Caseless",
    "Ammo_AC20_Caseless",
    "Ammo_LAC2_Caseless",
    "Ammo_LAC5_Caseless",
    "Ammo_LRM_Sguided",
    "Ammo_ATM3_ER",
    "Ammo_ATM3_HE",
    "Ammo_ATM6_ER",
    "Ammo_ATM6_HE",
    "Ammo_ATM9_ER",
    "Ammo_ATM9_HE",
    "Ammo_ATM12_ER",
    "Ammo_ATM12_HE",
    "SearchLight",
    "Sensors_10",
    "Sensors_20",
    "Sensors_30",
    "Sensors_40",
    "Sensors_50",
    "Sensors_60",
    "Sensors_70",
    "Sensors_80",
    "Sensors_90",
    "Sensors_100",
    "Myomer_10",
    "Myomer_20",
    "Myomer_30",
    "Myomer_40",
    "Myomer_50",
    "Myomer_60",
    "Myomer_70",
    "Myomer_80",
    "Myomer_90",
    "Myomer_100",
    "TripleMyomer_10",
    "TripleMyomer_20",
    "TripleMyomer_30",
    "TripleMyomer_40",
    "TripleMyomer_50",
    "TripleMyomer_60",
    "TripleMyomer_70",
    "TripleMyomer_80",
    "TripleMyomer_90",
    "TripleMyomer_100",
    "Internal_10",
    "Internal_20",
    "Internal_30",
    "Internal_40",
    "Internal_50",
    "Internal_60",
    "Internal_70",
    "Internal_80",
    "Internal_90",
    "Internal_100",
    "ES_Internal_10",
    "ES_Internal_20",
    "ES_Internal_30",
    "ES_Internal_40",
    "ES_Internal_50",
    "ES_Internal_60",
    "ES_Internal_70",
    "ES_Internal_80",
    "ES_Internal_90",
    "ES_Internal_100",
    "JumpJet_10",
    "JumpJet_20",
    "JumpJet_30",
    "JumpJet_40",
    "JumpJet_50",
    "JumpJet_60",
    "JumpJet_70",
    "JumpJet_80",
    "JumpJet_90",
    "JumpJet_100",
    "UpperArmActuator_10",
    "UpperArmActuator_20",
    "UpperArmActuator_30",
    "UpperArmActuator_40",
    "UpperArmActuator_50",
    "UpperArmActuator_60",
    "UpperArmActuator_70",
    "UpperArmActuator_80",
    "UpperArmActuator_90",
    "UpperArmActuator_100",
    "LowerArmActuator_10",
    "LowerArmActuator_20",
    "LowerArmActuator_30",
    "LowerArmActuator_40",
    "LowerArmActuator_50",
    "LowerArmActuator_60",
    "LowerArmActuator_70",
    "LowerArmActuator_80",
    "LowerArmActuator_90",
    "LowerArmActuator_100",
    "HandActuator_10",
    "HandActuator_20",
    "HandActuator_30",
    "HandActuator_40",
    "HandActuator_50",
    "HandActuator_60",
    "HandActuator_70",
    "HandActuator_80",
    "HandActuator_90",
    "HandActuator_100",
    "UpperLegActuator_10",
    "UpperLegActuator_20",
    "UpperLegActuator_30",
    "UpperLegActuator_40",
    "UpperLegActuator_50",
    "UpperLegActuator_60",
    "UpperLegActuator_70",
    "UpperLegActuator_80",
    "UpperLegActuator_90",
    "UpperLegActuator_100",
    "LowerLegActuator_10",
    "LowerLegActuator_20",
    "LowerLegActuator_30",
    "LowerLegActuator_40",
    "LowerLegActuator_50",
    "LowerLegActuator_60",
    "LowerLegActuator_70",
    "LowerLegActuator_80",
    "LowerLegActuator_90",
    "LowerLegActuator_100",
    "FootActuator_10",
    "FootActuator_20",
    "FootActuator_30",
    "FootActuator_40",
    "FootActuator_50",
    "FootActuator_60",
    "FootActuator_70",
    "FootActuator_80",
    "FootActuator_90",
    "FootActuator_100",
    "Engine_20",
    "Engine_40",
    "Engine_60",
    "Engine_80",
    "Engine_100",
    "Engine_120",
    "Engine_140",
    "Engine_160",
    "Engine_180",
    "Engine_200",
    "Engine_220",
    "Engine_240",
    "Engine_260",
    "Engine_280",
    "Engine_300",
    "Engine_320",
    "Engine_340",
    "Engine_360",
    "Engine_380",
    "Engine_400",
    "XL_Engine_20",
    "XL_Engine_40",
    "XL_Engine_60",
    "XL_Engine_80",
    "XL_Engine_100",
    "XL_Engine_120",
    "XL_Engine_140",
    "XL_Engine_160",
    "XL_Engine_180",
    "XL_Engine_200",
    "XL_Engine_220",
    "XL_Engine_240",
    "XL_Engine_260",
    "XL_Engine_280",
    "XL_Engine_300",
    "XL_Engine_320",
    "XL_Engine_340",
    "XL_Engine_360",
    "XL_Engine_380",
    "XL_Engine_400",
    "ICE_Engine_20",
    "ICE_Engine_40",
    "ICE_Engine_60",
    "ICE_Engine_80",
    "ICE_Engine_100",
    "ICE_Engine_120",
    "ICE_Engine_140",
    "ICE_Engine_160",
    "ICE_Engine_180",
    "ICE_Engine_200",
    "ICE_Engine_220",
    "ICE_Engine_240",
    "ICE_Engine_260",
    "ICE_Engine_280",
    "ICE_Engine_300",
    "ICE_Engine_320",
    "ICE_Engine_340",
    "ICE_Engine_360",
    "ICE_Engine_380",
    "ICE_Engine_400",
    "Light_Engine_20",
    "Light_Engine_40",
    "Light_Engine_60",
    "Light_Engine_80",
    "Light_Engine_100",
    "Light_Engine_120",
    "Light_Engine_140",
    "Light_Engine_160",
    "Light_Engine_180",
    "Light_Engine_200",
    "Light_Engine_220",
    "Light_Engine_240",
    "Light_Engine_260",
    "Light_Engine_280",
    "Light_Engine_300",
    "Light_Engine_320",
    "Light_Engine_340",
    "Light_Engine_360",
    "Light_Engine_380",
    "Light_Engine_400",
    "CO_Internal_10",
    "CO_Internal_20",
    "CO_Internal_30",
    "CO_Internal_40",
    "CO_Internal_50",
    "CO_Internal_60",
    "CO_Internal_70",
    "CO_Internal_80",
    "CO_Internal_90",
    "CO_Internal_100",
    "RE_Internal_10",
    "RE_Internal_20",
    "RE_Internal_30",
    "RE_Internal_40",
    "RE_Internal_50",
    "RE_Internal_60",
    "RE_Internal_70",
    "RE_Internal_80",
    "RE_Internal_90",
    "RE_Internal_100",
    "Gyro_1",
    "Gyro_2",
    "Gyro_3",
    "Gyro_4",
    "XL_Gyro_1",
    "XL_Gyro_2",
    "XL_Gyro_3",
    "XL_Gyro_4",
    "HD_Gyro_1",
    "HD_Gyro_2",
    "HD_Gyro_3",
    "HD_Gyro_4",
    "Compact_Gyro_1",
    "Compact_Gyro_2",
    "Compact_Gyro_3",
    "Compact_Gyro_4",
    "XXL_Engine_20",
    "XXL_Engine_40",
    "XXL_Engine_60",
    "XXL_Engine_80",
    "XXL_Engine_100",
    "XXL_Engine_120",
    "XXL_Engine_140",
    "XXL_Engine_160",
    "XXL_Engine_180",
    "XXL_Engine_200",
    "XXL_Engine_220",
    "XXL_Engine_240",
    "XXL_Engine_260",
    "XXL_Engine_280",
    "XXL_Engine_300",
    "XXL_Engine_320",
    "XXL_Engine_340",
    "XXL_Engine_360",
    "XXL_Engine_380",
    "XXL_Engine_400",
    "Compact_Engine_20",
    "Compact_Engine_40",
    "Compact_Engine_60",
    "Compact_Engine_80",
    "Compact_Engine_100",
    "Compact_Engine_120",
    "Compact_Engine_140",
    "Compact_Engine_160",
    "Compact_Engine_180",
    "Compact_Engine_200",
    "Compact_Engine_220",
    "Compact_Engine_240",
    "Compact_Engine_260",
    "Compact_Engine_280",
    "Compact_Engine_300",
    "Compact_Engine_320",
    "Compact_Engine_340",
    "Compact_Engine_360",
    "Compact_Engine_380",
    "Compact_Engine_400",
)

INTERNALSWEIGHT = (
    102,						# ShoulderOrHip
    102,						# UpperActuator
    102,						# LowerActuator
    102,						# HandOrFootActuator
    204,						# LifeSupport
    102,						# Sensors
    512,						# Cockpit
    1024,						# Engine
    512,						# Gyro
    204,						# HeatSink
    204,						# JumpJet
    51,							# Case
    153,						# FerroFibrous
    153,						# EndoSteel
    51,							# TripleStrengthMyomer
    204,						# TargetingComputer
    51,							# Masc
    512,						# C3Master
    102,						# C3Slave
    102,						# BeagleProbe
    153,						# ArtemisIV
    204,						# Ecm
    51,							# Axe
    25,							# Sword
    102,						# Mace
    75,							# Claw
    1024,						# DSAeroDoor
    1024,						# DSMechDoor
    102,						# Fuel_Tank
    51,							# TAG
    1024,						# DSVehicleDoor
    1024,						# DSCargoDoor
    306,						# LAM_Equipment
    306,						# CaseII
    3,							# StealthArmor
    1024,						# NullSig_Device
    512,						# C3i
    204,						# AngelECM
    7,							# HvyFerroFibrous
    1,							# LtFerroFibrous
    102,						# BloodhoundProbe
    2,							# PurifierArmor
    102,						# KageStealthUnit
    102,						# AchileusStealthUnit
    102,						# InfiltratorStealthUnit
    102,						# InfiltratorIIStealthUnit
    1024,						# Dual_Saw
    512,						# Light_BAP
)

CARGOWEIGHT = (
    1024,						# Ammo_LBX2
    1024,						# Ammo_LBX5_LBX
    1024,						# Ammo_LBX10_LBX
    1024,						# Ammo_LBX20_LBX
    1024,						# Ammo_LRM
    1024,						# Ammo_SRM
    1024,						# Ammo_SSRM
    1024,						# Ammo_LRM_NARC
    1024,						# Ammo_SRM_NARC
    1024,						# Ammo_SSRM_NARC
    1024,						# Ammo_LRM_Artemis
    1024,						# Ammo_SRM_Artemis
    1024,						# Ammo_SSRM_Artemis
    102,						# Petroleum
    102,						# Phosphorus
    102,						# Hydrogen
    204,						# Gold
    51,							# Natural_Extracts
    10,							# Marijuana
    10,							# Sulfur
    10,							# Sodium
    306,						# Plutonium
    51,							# Ore
    204,						# Steel
    51,							# Plastics
    8,							# Medical_Supplies
    306,						# Computers
    204,						# Explosives
    32,							# ES_Internal
    57,							# FF_Armor
    512,						# XL_Engine
    342,						# Double_Heatsink
    512,						# ICE_Engine
    51,							# Electric
    64,							# Internal
    64,							# Armor
    102,						# Actuator
    10,							# Aero_Fuel
    20,							# DS_Fuel
    2,							# VTOL_Fuel
    1024,						# Ammo_LRM_Swarm
    1024,						# Ammo_LRM_Swarm1
    1024,						# Ammo_SRM_Inferno
    1024,						# XXL_Engine
    2048,						# Compact_Engine
    6,							# HD_Armor
    4,							# RE_Internals
    2,							# CO_Internals
    1024,						# Ammo_MRM
    512,						# Light_Engine
    62,							# CaseII
    3,							# STH_Armor
    1024,						# NullSigSys
    80,							# Silicon
    7,							# HVY_FF_Armor
    1,							# LT_FF_Armor
    1024,						# Ammo_iNARC_Explosive
    1024,						# Ammo_iNARC_Haywire
    1024,						# Ammo_iNARC_ECM
    1024,						# Ammo_iNARC_Nemesis
    1024,						# Ammo_AC2_AP
    1024,						# Ammo_AC5_AP
    1024,						# Ammo_AC10_AP
    1024,						# Ammo_AC20_AP
    1024,						# Ammo_LAC2_AP
    1024,						# Ammo_LAC5_AP
    1024,						# Ammo_AC2_Flechette
    1024,						# Ammo_AC5_Flechette
    1024,						# Ammo_AC10_Flechette
    1024,						# Ammo_AC20_Flechette
    1024,						# Ammo_LAC2_Flechette
    1024,						# Ammo_LAC5_Flechette
    1024,						# Ammo_AC2_Incendiary
    1024,						# Ammo_AC5_Incendiary
    1024,						# Ammo_AC10_Incendiary
    1024,						# Ammo_AC20_Incendiary
    1024,						# Ammo_LAC2_Incendiary
    1024,						# Ammo_LAC5_Incendiary
    1024,						# Ammo_AC2_Precision
    1024,						# Ammo_AC5_Precision
    1024,						# Ammo_AC10_Precision
    1024,						# Ammo_AC20_Precision
    1024,						# Ammo_LAC2_Precision
    1024,						# Ammo_LAC5_Precision
    1024,						# Ammo_LR_DFM
    1024,						# Ammo_SR_DFM
    1024,						# Ammo_SLRM
    1024,						# Ammo_ELRM
    102,						# BSuit_Sensor
    61,							# BSuit_LifeSupport
    10,							# BSuit_Electronic
    306,						# Oil
    102,						# Water
    204,						# Earth
    21,							# Oxygen
    102,						# Nitrogen
    102,						# Nickel
    204,						# Steel
    204,						# Iron
    204,						# Brass
    204,						# Platinum
    204,						# Copper
    204,						# Aluminum
    61,							# Consumer_Good
    312,						# Machinery
    102,						# Slaves
    21,							# Timbiqui_Dark
    10,							# Cocaine
    10,							# Heroine
    424,						# Marble
    408,						# Glass
    204,						# Diamond
    306,						# Coal
    204,						# Food
    102,						# Zinc
    204,						# Fabric
    204,						# Clothing
    408,						# Wood
    204,						# Pulp
    520,						# Lumber
    204,						# Rubber
    102,						# Seeds
    102,						# Fertilizer
    102,						# Salt
    204,						# Lithium
    102,						# Helium
    306,						# Larium
    306,						# Uranium
    306,						# Iridium
    408,						# Titanium
    306,						# Concrete
    204,						# FerroCrete
    204,						# Building_Supplies
    204,						# Kevlar
    204,						# Waste
    308,						# Livestock
    102,						# Paper
    1024,						# XL_Gyro
    2048,						# HeavyDuty_Gyro
    2048,						# Compact_Gyro
    2048,						# Compact_HeatSink
    1024,						# Ammo_LRM_Stinger
    1024,						# Ammo_AC2_Caseless
    1024,						# Ammo_AC5_Caseless
    1024,						# Ammo_AC10_Caseless
    1024,						# Ammo_AC20_Caseless
    1024,						# Ammo_LAC2_Caseless
    1024,						# Ammo_LAC5_Caseless
    1024,						# Ammo_LRM_Sguided
    204,						# SearchLight
    1024,						# ATM3 ER
    1024,						# ATM3 HE
    1024,						# ATM6 ER
    1024,						# ATM6 HE
    1024,						# ATM9 ER
    1024,						# ATM9 HE
    1024,						# ATM12 HE
    1024,						# ATM12 ER
    102,						# Sensors_10
    204,						# Sensors_20
    306,						# Sensors_30
    408,						# Sensors_40
    510,						# Sensors_50
    612,						# Sensors_60
    714,						# Sensors_70
    816,						# Sensors_80
    918,						# Sensors_90
    1020,						# Sensors_100
    102,						# Myomer_10
    102,						# Myomer_20
    102,						# Myomer_30
    102,						# Myomer_40
    102,						# Myomer_50
    102,						# Myomer_60
    102,						# Myomer_70
    102,						# Myomer_80
    102,						# Myomer_90
    102,						# Myomer_100
    102,						# TripleMyomer_10
    102,						# TripleMyomer_20
    102,						# TripleMyomer_30
    102,						# TripleMyomer_40
    102,						# TripleMyomer_50
    102,						# TripleMyomer_60
    102,						# TripleMyomer_70
    102,						# TripleMyomer_80
    102,						# TripleMyomer_90
    102,						# TripleMyomer_100
    128,						# Internal_10
    128,						# Internal_20
    128,						# Internal_30
    128,						# Internal_40
    128,						# Internal_50
    128,						# Internal_60
    128,						# Internal_70
    128,						# Internal_80
    128,						# Internal_90
    128,						# Internal_100
    128,						# ES_Internal_10
    128,						# ES_Internal_20
    128,						# ES_Internal_30
    128,						# ES_Internal_40
    128,						# ES_Internal_50
    128,						# ES_Internal_60
    128,						# ES_Internal_70
    128,						# ES_Internal_80
    128,						# ES_Internal_90
    128,						# ES_Internal_100
    102,						# JumpJet_10
    204,						# JumpJet_20
    306,						# JumpJet_30
    408,						# JumpJet_40
    510,						# JumpJet_50
    612,						# JumpJet_60
    714,						# JumpJet_70
    816,						# JumpJet_80
    918,						# JumpJet_90
    1020,						# JumpJet_100
    8,							# UpperArmActuator_10
    8,							# UpperArmActuator_20
    8,							# UpperArmActuator_30
    8,							# UpperArmActuator_40
    8,							# UpperArmActuator_50
    8,							# UpperArmActuator_60
    8,							# UpperArmActuator_70
    8,							# UpperArmActuator_80
    8,							# UpperArmActuator_90
    8,							# UpperArmActuator_100
    8,							# LowerArmActuator_10
    8,							# LowerArmActuator_20
    8,							# LowerArmActuator_30
    8,							# LowerArmActuator_40
    8,							# LowerArmActuator_50
    8,							# LowerArmActuator_60
    8,							# LowerArmActuator_70
    8,							# LowerArmActuator_80
    8,							# LowerArmActuator_90
    8,							# LowerArmActuator_100
    8,							# HandActuator_10
    8,							# HandActuator_20
    8,							# HandActuator_30
    8,							# HandActuator_40
    8,							# HandActuator_50
    8,							# HandActuator_60
    8,							# HandActuator_70
    8,							# HandActuator_80
    8,							# HandActuator_90
    8,							# HandActuator_100
    8,							# UpperLegActuator_10
    8,							# UpperLegActuator_20
    8,							# UpperLegActuator_30
    8,							# UpperLegActuator_40
    8,							# UpperLegActuator_50
    8,							# UpperLegActuator_60
    8,							# UpperLegActuator_70
    8,							# UpperLegActuator_80
    8,							# UpperLegActuator_90
    8,							# UpperLegActuator_100
    8,							# LowerLegActuator_10
    8,							# LowerLegActuator_20
    8,							# LowerLegActuator_30
    8,							# LowerLegActuator_40
    8,							# LowerLegActuator_50
    8,							# LowerLegActuator_60
    8,							# LowerLegActuator_70
    8,							# LowerLegActuator_80
    8,							# LowerLegActuator_90
    8,							# LowerLegActuator_100
    8,							# FootActuator_10
    8,							# FootActuator_20
    8,							# FootActuator_30
    8,							# FootActuator_40
    8,							# FootActuator_50
    8,							# FootActuator_60
    8,							# FootActuator_70
    8,							# FootActuator_80
    8,							# FootActuator_90
    8,							# FootActuator_100
    51,							# Engine_20
    102,						# Engine_40
    153,						# Engine_60
    204,						# Engine_80
    255,						# Engine_100
    306,						# Engine_120
    357,						# Engine_140
    408,						# Engine_160
    459,						# Engine_180
    510,						# Engine_200
    561,						# Engine_220
    612,						# Engine_240
    763,						# Engine_260
    814,						# Engine_280
    865,						# Engine_300
    916,						# Engine_320
    967,						# Engine_340
    1018,						# Engine_360
    1070,						# Engine_380
    1020,						# Engine_400
    51,							# XL_Engine_20
    102,						# XL_Engine_40
    153,						# XL_Engine_60
    204,						# XL_Engine_80
    255,						# XL_Engine_100
    306,						# XL_Engine_120
    357,						# XL_Engine_140
    408,						# XL_Engine_160
    459,						# XL_Engine_180
    510,						# XL_Engine_200
    561,						# XL_Engine_220
    612,						# XL_Engine_240
    763,						# XL_Engine_260
    814,						# XL_Engine_280
    865,						# XL_Engine_300
    916,						# XL_Engine_320
    967,						# XL_Engine_340
    1018,						# XL_Engine_360
    1070,						# XL_Engine_380
    1020,						# XL_Engine_400
    51,							# ICE_Engine_20
    102,						# ICE_Engine_40
    153,						# ICE_Engine_60
    204,						# ICE_Engine_80
    255,						# ICE_Engine_100
    306,						# ICE_Engine_120
    357,						# ICE_Engine_140
    408,						# ICE_Engine_160
    459,						# ICE_Engine_180
    510,						# ICE_Engine_200
    561,						# ICE_Engine_220
    612,						# ICE_Engine_240
    763,						# ICE_Engine_260
    814,						# ICE_Engine_280
    865,						# ICE_Engine_300
    916,						# ICE_Engine_320
    967,						# ICE_Engine_340
    1018,						# ICE_Engine_360
    1070,						# ICE_Engine_380
    1020,						# ICE_Engine_400
    51,							# Light_Engine_20
    102,						# Light_Engine_40
    153,						# Light_Engine_60
    204,						# Light_Engine_80
    255,						# Light_Engine_100
    306,						# Light_Engine_120
    357,						# Light_Engine_140
    408,						# Light_Engine_160
    459,						# Light_Engine_180
    510,						# Light_Engine_200
    561,						# Light_Engine_220
    612,						# Light_Engine_240
    763,						# Light_Engine_260
    814,						# Light_Engine_280
    865,						# Light_Engine_300
    916,						# Light_Engine_320
    967,						# Light_Engine_340
    1018,						# Light_Engine_360
    1070,						# Light_Engine_380
    1020,						# Light_Engine_400
    128,						# CO_Internal_10
    128,						# CO_Internal_20
    128,						# CO_Internal_30
    128,						# CO_Internal_40
    128,						# CO_Internal_50
    128,						# CO_Internal_60
    128,						# CO_Internal_70
    128,						# CO_Internal_80
    128,						# CO_Internal_90
    128,						# CO_Internal_100
    128,						# RE_Internal_10
    128,						# RE_Internal_20
    128,						# RE_Internal_30
    128,						# RE_Internal_40
    128,						# RE_Internal_50
    128,						# RE_Internal_60
    128,						# RE_Internal_70
    128,						# RE_Internal_80
    128,						# RE_Internal_90
    128,						# RE_Internal_100
    1024,						# Gyro_1
    2048,						# Gyro_2
    3072,						# Gyro_3
    4096,						# Gyro_4
    1024,						# XL_Gyro_1
    2048,						# XL_Gyro_2
    3072,						# XL_Gyro_3
    4096,						# XL_Gyro_4
    1024,						# HD_Gyro_1
    2048,						# HD_Gyro_2
    3072,						# HD_Gyro_3
    4096,						# HD_Gyro_4
    1024,						# Compact_Gyro_1
    2048,						# Compact_Gyro_2
    3072,						# Compact_Gyro_3
    4096,						# Compact_Gyro_4
    51,							# XXL_Engine_20
    102,						# XXL_Engine_40
    153,						# XXL_Engine_60
    204,						# XXL_Engine_80
    255,						# XXL_Engine_100
    306,						# XXL_Engine_120
    357,						# XXL_Engine_140
    408,						# XXL_Engine_160
    459,						# XXL_Engine_180
    510,						# XXL_Engine_200
    561,						# XXL_Engine_220
    612,						# XXL_Engine_240
    763,						# XXL_Engine_260
    814,						# XXL_Engine_280
    865,						# XXL_Engine_300
    916,						# XXL_Engine_320
    967,						# XXL_Engine_340
    1018,						# XXL_Engine_360
    1070,						# XXL_Engine_380
    1020,						# XXL_Engine_400
    51,							# Compact_Engine_20
    102,						# Compact_Engine_40
    153,						# Compact_Engine_60
    204,						# Compact_Engine_80
    255,						# Compact_Engine_100
    306,						# Compact_Engine_120
    357,						# Compact_Engine_140
    408,						# Compact_Engine_160
    459,						# Compact_Engine_180
    510,						# Compact_Engine_200
    561,						# Compact_Engine_220
    612,						# Compact_Engine_240
    763,						# Compact_Engine_260
    814,						# Compact_Engine_280
    865,						# Compact_Engine_300
    916,						# Compact_Engine_320
    967,						# Compact_Engine_340
    1018,						# Compact_Engine_360
    1070,						# Compact_Engine_380
    1020,						# Compact_Engine_400
)

BOMBS = ("10_Inferno", "10_Cluster", "10_Standard", "50_Inferno", "50_Cluster", "50_Standard", "100_Inferno", "100_Cluster", "100_Standard")
