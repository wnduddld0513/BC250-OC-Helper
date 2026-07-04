# BC250 OC Helper

A simple GUI overclock tool to modify BC-250's CPU and GPU.

## DISCLAIMER

**Overclocking is done at your own risk!** Failure to exercise caution can result in permanent damage to your hardware. 

Increasing the CPU frequency without undervolting will result in uncapped Vid scaling, which can destroy your hardware. Always make sure that the CPU core voltage ("Vid") does not exceed **1.325 V** under any circumstances! Please monitor your hardware closely and always perform stress testing after changing parameters.

## Installation

You can easily install the application, along with all required dependencies and background governors, using the automated installation script.

Run the following command in your terminal:

```bash
curl -sSL [https://raw.githubusercontent.com/wnduddld0513/BC-250-OC-Helper/main/install.sh](https://raw.githubusercontent.com/wnduddld0513/BC-250-OC-Helper/main/install.sh) | bash
