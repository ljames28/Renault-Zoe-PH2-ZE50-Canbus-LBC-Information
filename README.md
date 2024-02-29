# Zoe PH2 ZE50 EV Canbus / LBC Information
 
This repository contains information about the ZE50 Renault Zoe PH2 Pack. There are CAN bus logs taken from a Zoe PH2 ZE50 car. They were captured on the 'HEV-CAN' near the battery. The 'HEV-CAN' includes the BMS(LBC 938), HEVC(946) and PEC(2325).

There is a can frames Excel file, which details exactly which frames the LBC (Lithium Battery Controller) listens to, as many bus frames are irrelevant to the LBC

By replaying the can bus log to a ZE50 battery, it is possible to wake the battery up, and read information via 29bit CAN frames to address 18DAF1DB. However, the battery will be confused and will not balance. To properly emulate the car so that the battery is happy, you will need to send correct timing information and correct checksums.

There is an example python script which you can you use to set up your own code to talk to the battery. This script will not run on its own.

Please note the 29bit frames have been stripped from all logs, as these contain battery identifier information during charge initiation.

The 52kwh pack is 400V nominal, 96s2p, 12 modules. Each module is roughly 4450wh. Each module contains 16 LG XE78 cells.

The main processor inside the pack is an Infineon/Cypress CY91F526B

If the pack is in a state where it is confused about the time, you may need to reset it's NVROL memory. However, if the power is later power cycled, it will revert back to his previous confused state. Therefore, after resetting the NVROL you must enable "temporisation before sleep", and then stop streaming 373. It will then save the data and go to sleep. When the pack is confused, the state of charge may reset back to incorrect value every time the power is reset which can be dangerous. In this state, the voltage will still be accurate.


You will want to reference the helpful 29bit frame file here https://github.com/fesch/CanZE/blob/master/app/src/main/assets/ZOE_Ph2/LBC_Fields.csv



#Commands

NVROL Reset: "cansend can1 18DADBF1#021003AAAAAAAAAA && sleep 0.1 &&  cansend can1 18DADBF1#043101B00900AAAA"
Enable temporisation before sleep: "cansend can1 18DADBF1#021003AAAAAAAAAA && sleep 0.1 &&   cansend can1 18DADBF1#042E928101AAAAAA"
