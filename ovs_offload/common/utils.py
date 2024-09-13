#!/usr/bin/python
#
# Copyright 2022-2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Common python APIs and utilities for the Intel® Infrastructure
# Processing Unit (Intel® IPU).

import logging
import subprocess, os, time, re
import yaml

def fetch_configurations(config_file=''):
    with open(config_file, "r") as file:
        config_data = yaml.safe_load(file)
    return config_data

#Fetch test configuration
test_config = fetch_configurations(f'{os.path.dirname(os.path.abspath(__file__))}/../config.yaml')

def run_cmd(cmd, output=False, check_returncode=True):
    """
    Execute a command in a subprocess.
    :param cmd: The command to be executed as a string.
    :param output: If True, capture and return the command's stdout.
    :param check_returncode: If True, check the command's return code and raise an error if not 0.
    :return: The stdout of the command if output is True, otherwise None.
    """
    print(f'Executing: {cmd}')
    # Use a context manager to ensure the subprocess is cleaned up after execution
    with subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE if output else None, stderr=subprocess.PIPE, encoding="utf-8") as s:
        outs, errs = s.communicate() if output else (None, None)
        # Check the return code if required
        if check_returncode and s.returncode != 0:
            raise subprocess.CalledProcessError(s.returncode, cmd, output=outs, stderr=errs)
        return outs.strip() if output else None

def ssh_command(server_name, command, output=True, check_returncode=True):
    """
    Execute a command on a remote server via SSH.
    :param server_name: The name of the server ('host', 'imc', or 'acc').
    :param command: The command to be executed on the remote server.
    :return: A dictionary with the return code and the command's output.
    """
    imc_ip = test_config['imc']['ssh']['ip']
    acc_ip = test_config['acc']['ssh']['ip']
    # SSH command templates
    imc_access = f'ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@{imc_ip}'
    acc_access = f'{imc_access} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@{acc_ip}'

    # Determine the appropriate SSH command based on the server name
    if server_name == 'host':
        full_cmd = command
    elif server_name == 'imc':
        full_cmd = f'{imc_access} "{command}"'
    elif server_name == 'acc':
        full_cmd = f'{acc_access} "{command}"'
    else:
        raise ValueError(f"Unknown server name: {server_name}")

    # Execute the command and capture the output
    output = run_cmd(full_cmd, output = output, check_returncode = check_returncode)

    # Return the result as a dictionary
    return {'rc': 0, 'output': output}


def copy_scripts(host_path='ovs_offload_lnw_scripts', imc_path = '/mnt/imc/p4_test', acc_path = '/opt/p4/p4sde/p4_test'):
    """
    Copies configuration scripts from the host to the IMC and then to the ACC.

    :param host_path: Path to the configuration scripts on the host machine
    :param imc_path: Destination path on the IMC
    :param acc_path: Destination path on the ACC
    """
    imc_ip = test_config['imc']['ssh']['ip']
    acc_ip = test_config['acc']['ssh']['ip']

    command = f'mkdir -p {imc_path}'
    try:
        result = ssh_command('imc', command)
    except Exception as e:
        print(f"Failed with exception:\n{e}")

    command = f'mkdir -p {acc_path}'
    try:
        result = ssh_command('acc', command)
    except Exception as e:
        print(f"Failed with exception:\n{e}")

    # Copy the configuration scripts from host to IMC
    command = f'scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r {host_path}  root@{imc_ip}:{imc_path}/'
    try:
        result = ssh_command('host', command)
    except Exception as e:
        print(f"Failed with exception:\n{e}")

    command = f'chmod +x {imc_path}/{host_path}/*'
    try:
        result = ssh_command('imc', command)
    except Exception as e:
        print(f"Failed with exception:\n{e}")

    # Copy the configuration scripts from IMC to ACC
    command = f'scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r {imc_path}/{host_path} root@{acc_ip}:{acc_path}/'
    try:
        result = ssh_command('imc', command)
    except Exception as e:
        print(f"Failed with exception:\n{e}")

    command = f'chmod +x {acc_path}/{host_path}/*'
    try:
        result = ssh_command('acc', command)
    except Exception as e:
        print(f"Failed with exception:\n{e}")


def get_interface_info(server_name, interface_name):
    """
    Retrieve information about a network interface on a remote server.

    :param server_name: The name of the server where the interface is located.
    :param interface_name: The name of the network interface to query.
    :return: A dictionary containing various pieces of information about the interface.
    """
    # Initialize an empty dictionary to store interface information
    interface_info = {}

    # Define a mapping of server names to host IDs
    host_id = {
        'host': '0x0',
        'acc': '0x4',
        'imc': '0x5'
    }

    # Command to get basic interface information using ifconfig
    cmd = f"ifconfig {interface_name}"
    try:
        result = ssh_command(server_name, cmd)
    except Exception as e:
        logging.error(f"Failed to run ifconfig on '{interface_name}': {e}")
        return interface_info

    output = result['output']

    # Regex patterns to extract IP, MAC, and other fields
    ip_pattern = re.compile(r'inet (\d+\.\d+\.\d+\.\d+)')
    mac_pattern = re.compile(r'ether ([0-9a-fA-F:]{17})')
    mtu_pattern = re.compile(r'mtu (\d+)')

    # Search for patterns in the output and populate the dictionary
    interface_info['ip'] = ip_pattern.search(output).group(1) if ip_pattern.search(output) else None
    interface_info['mac'] = mac_pattern.search(output).group(1) if mac_pattern.search(output) else None
    interface_info['mtu'] = mtu_pattern.search(output).group(1) if mtu_pattern.search(output) else None

    # Command to get detailed interface information using ethtool
    cmd = f"ethtool -i {interface_name}"
    try:
        result = ssh_command(server_name, cmd)
    except Exception as e:
        logging.warning(f"Failed to run ethtool on '{interface_name}': {e}")
        return interface_info

    output = result['output']

    # Parse ethtool output and add to the dictionary
    for line in output.split('\n'):
        field = line.split(': ')
        if len(field) == 2:
            interface_info[field[0].strip()] = field[1].strip()

    # Check if the driver is not 'idpf' and return the info collected so far
    if interface_info.get('driver') != 'idpf':
        return interface_info

    # Command to get additional interface information for 'idpf' interface from IMC
    cmd = f"cli_client -q -c | grep 'host_id: {host_id[server_name]}' | grep '{interface_info['mac']}'"
    try:
        result = ssh_command('imc', cmd)
    except Exception as e:
        logging.warning(f"Failed to run cli_client on '{interface_name}': {e}")
        return interface_info

    output = result['output']

    # Regex pattern to extract additional fields for 'idpf' driver
    pattern = re.compile(r'fn_id:\s+(\w+)\s+host_id:\s+(\w+)\s+is_vf:\s+(\w+)\s+vsi_id:\s+(\w+)\s+vport_id\s+(\w+)\s+is_created:\s+(\w+)\s+is_enabled:\s+(\w+)\s+mac\s+addr:\s+([0-9a-fA-F:]{17})')
    match = pattern.search(output)

    # Populate the dictionary with additional information if available
    if match:
        interface_info.update({
            'fn_id': match.group(1),
            'host_id': match.group(2),
            'is_vf': match.group(3),
            'vsi_id': match.group(4),
            'vport_id': match.group(5),
            'is_created': match.group(6),
            'is_enabled': match.group(7),
            'mac_addr': match.group(8)
        })

        # Calculate additional fields based on 'vsi_id'
        if interface_info['vsi_id']:
            interface_info['vsi_num'] = str(int(interface_info['vsi_id'], 16))
            port_offset = str(int(interface_info['vsi_id'], 16) + 16)
            interface_info['port'] = port_offset

    return interface_info


def ping_test(dst_ip, count=4, vm = None):
    if vm:
        cmd = f"ip netns exec {vm} ping {dst_ip} -c {count}"
    else:
        cmd = f"ping {dst_ip} -c {count}"
    try:
        result = run_cmd(cmd, output=True)
        pkt_loss = 100
        if result:
            match = re.search('(\d*)% packet loss', result)
            if match:
                pkt_loss = int(match.group(1))
            if f"{count} received, 0% packet loss" in result:
                print(f"PASS: Ping successful to destination {dst_ip}\n")
                return True
            else:
                raise RuntimeError(f"FAIL: Ping Failed to destination {dst_ip} with" f" {pkt_loss}% loss\n")
    except Exception as E:
        print(f"Ping run failed with error:'{E}'\n")
        return False

class tmux_term:
    def __init__(self, tmux_name="", tmux_override=False):
        # Initialize a new tmux terminal session
        if not tmux_name:
            raise ValueError("Error: No tmux name specified!")
        self.tmux_name = tmux_name

        # Check if the specified tmux session already exists
        command = 'tmux ls'
        try:
            result = ssh_command('host', command, check_returncode=False)
        except Exception as e:
            raise Exception(f"Failed to list tmux sessions with exception:\n{e}")

        # Parse the output to find an existing session
        lines = result['output']
        found = any(self.tmux_name in line for line in lines.split('\n'))

        # If the session is found and override is allowed, kill the existing session
        if found and tmux_override:
            command = f'tmux kill-session -t {self.tmux_name}'
            ssh_command('host', command)

        # If the session was not found or was killed, create a new one
        if not found or tmux_override:
            command = f'tmux new-session -d -s {self.tmux_name}'
            ssh_command('host', command)

    def tmux_send_keys(self, cmd, delay=1, output=True):
        # Send a command to the tmux session and optionally capture the output
        time.sleep(0.5)  # Short delay before sending the command

        if output:
            # Set up piping to capture the output of the command
            output_file = os.path.join(os.getcwd(), 'tmux_output.txt')
            command = f'tmux pipe-pane -t {self.tmux_name} "cat > {output_file}"'
            ssh_command('host', command)

        # Send the actual command to the tmux session
        command = f'tmux send-keys -t {self.tmux_name} "{cmd}" C-m'
        ssh_command('host', command)

        if output:
            # Wait for the specified delay to allow the command to execute and output to be captured
            if delay > 0:
                time.sleep(delay)

            # Stop piping the output
            command = f'tmux pipe-pane -t {self.tmux_name}'
            ssh_command('host', command)

            # Read the captured output from the file
            with open(output_file, "r") as f:
                result = f.read()

        return result
