import json
import os

AEVO_CONTRACT = '0x80d40e32FAD8bE8da5C6A42B8aF1E181984D137c'
USDC_CONTRACT = '0xff970a61a04b1ca14834a43f5de4533ebddb5cc8'

# Get the directory of the current script
dir_path = os.path.dirname(os.path.realpath(__file__))

# Adjust the path to locate the ABI files correctly
aevo_abi_path = os.path.join(dir_path, '..', 'assets', 'abi', 'aevo_abi.json')
erc20_abi_path = os.path.join(dir_path, '..', 'assets', 'abi', 'erc20.json')

# Now use these paths to open your files
with open(aevo_abi_path, 'r') as file:
    AEVO_ABI = json.load(file)

with open(erc20_abi_path, 'r') as file:
    ERC20_ABI = json.load(file)
