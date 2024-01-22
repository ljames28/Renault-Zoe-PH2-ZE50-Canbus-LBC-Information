# Zoe PH2 EV Canbus Information
 
This repository contains various CAN bus logs and other information taken from a Zoe PH2 ZE50 car. They were captured on the 'HEV-CAN' near the battery. The 'HEV-CAN' includes the BMS(LBC 938), HEVC(946) and PEC(2325).

The LBC file is very basic. The only known frames are are HVB_CellVoltage and HVB_ProbeTemp

By replaying the can bus log to a ZE50 battery, it is possible to wake the battery up, and read information via 29bit CAN frames to address 18DAF1DB. However, the battery is unlikely to balance so at the moment this cannot be used for reliable static storage.

Please note the 29bit frames have been stripped from all logs, as these contain battery identifier information during charge initiation.

The 52kwh pack is 400V nominal, 96s2p, 12 modules. Each module is roughly 4450wh. Each module contains 16 LG XE78 cells.

The main processor inside the pack is an Infineon/Cypress CY91F526B