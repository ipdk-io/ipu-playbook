#!/usr/bin/python
#
# Copyright 2022-2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Python tool to setup Linux Networking with OVS Offload on Intel® Infrastructure Processing Unit (Intel® IPU)

import sys,argparse
import os

# Add the parent directory to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.utils import *

def build_p4rt_config(test_setup = None):

    if test_setup == None:
        print("Unable to parse the config.yaml to generate test configuration")
        sys.exit()

    host_idpf_intf= test_setup.test_config['test_params']['idpf_interface']
    vf_list = test_setup.test_config['test_params']['vf_interfaces']
    acc_pr_list = test_setup.test_config['test_params']['acc_pr_interfaces']
    vm_ip_list = test_setup.test_config['test_params']['ip_list']
    path = test_setup.test_config['test_params']['host_path']
    comm_ip_host = test_setup.test_config['test_params']['comm_ip_host']
    comm_ip_acc = test_setup.test_config['test_params']['comm_ip_acc']
    ipsec_host = test_setup.test_config['test_params']['ipsec_host']
    local_vxlan_tunnel_mac =  test_setup.test_config['test_params']['local_vxlan_tunnel_mac']
    remote_vxlan_ip = test_setup.test_config['test_params']['remote_vxlan_ip']
    remote_vxlan_mac = test_setup.test_config['test_params']['remote_vxlan_mac']
    ipu_sdk_path = test_setup.test_config['test_params']['ipu_sdk_path']

    print("---------- Generating Configs to run infrap4d, p4rt, OVS and IPsec ----------")

    if len(vf_list) != len(acc_pr_list):
        print("ERROR: number of vfs and ACC PRs should be the same")
        return None

    file = f'{path}/1_host_idpf.sh'
    host_idpf = 'cat <<EOF > ./'+file+'''
#!/bin/sh
#Load the driver
echo "Load the IDPF Driver on the Host"
rmmod idpf
sleep 10

echo "stop firewalld"
systemctl stop firewalld

#Load the driver
echo "Load the IDPF Driver on the Host"
modprobe idpf
sleep 10

echo ""
echo "Check the Interfaces are up"
ip -br a
#Setup number of sriov devices on the IDPF interface
echo "Create SRIOV VFs on IDPF interface '''+host_idpf_intf+'''"
echo 8 > /sys/class/net/'''+host_idpf_intf+'''/device/sriov_numvfs

echo ""
echo "Wait for the interfaces to come up"
sleep 10
ip -br a
EOF
'''
    host_command_list = [f"mkdir -p {path}",
                         host_idpf,
                         f"chmod +x ./{file}",
                         f"./{file}",
                         "modinfo idpf | grep version",
                         f"ethtool -i {host_idpf_intf} | grep -A 1 idpf"]


    file = f'{path}/setup_host_comm_channel.sh'
    host_comm_channel = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo ""
echo "Assign IP to IDPF_COMMS_VPORT_2 for host acc comm channel"

nmcli device set '''+host_idpf_intf+'''d2 managed no
ip addr add '''+comm_ip_host+'''/24 dev '''+host_idpf_intf+'''d2
ip link set up dev '''+host_idpf_intf+'''d2

EOF
'''
    host_command_list.append(host_comm_channel)
    host_command_list.append(f"chmod +x ./{file}")

    for command in host_command_list:
        try:
            result = test_setup.ssh_command('host', command)
        except Exception as e:
            print(f"Failed with exception:\n{e}")
    time.sleep(5)

    mac_list = []
    vf_to_acc = ''
    phy_to_acc = ''
    vf_to_vm = ''
    ovs_vxlan = ''
    local_vtep = test_setup.test_config['test_params']['local_vtep']
    remote_vtep = test_setup.test_config['test_params']['remote_vtep']
    local_br_tun = test_setup.test_config['test_params']['local_br_tun_ip']
    remote_br_tun = test_setup.test_config['test_params']['remote_br_tun_ip']
    comm_ip_acc: test_setup.test_config['test_params']['comm_ip_acc']

    vm_id = 0
    command_list = []
    cmd = f"mkdir -p {path}"
    command_list.append(cmd)
    vf_list_len = len(vf_list)
    for i in range(vf_list_len):
        print("vf list len {} i is {} vf_list is {}".format(vf_list_len, i, vf_list[i]))
        if str(vf_list[i]) == '0' or str(vf_list[i]) == '1':
        #Physical port   VSI_ID  PORT             ACC port representer  VSI_ID    PORT
        #Phy port 0      (0x0)    0     <---->    enp0s1f0d10         (0x11) 17   33
            print(acc_pr_list[i])
            acc_pr = test_setup.get_interface_info(server_name='acc', interface_name=acc_pr_list[i])
            phy_to_acc += f"""echo ""
echo "IPU Physical Port {vf_list[i]} maps to "
echo "ACC IDPF Interface {acc_pr_list[i]} MAC ({acc_pr['mac']})  VSI ({acc_pr['vsi_id']}:{acc_pr['vsi_num']})  PORT ({acc_pr['port']})"
p4rt-ctl add-entry br0 linux_networking_control.rx_source_port "vmeta.common.port_id={vf_list[i]},zero_padding=0,action=linux_networking_control.set_source_port({vf_list[i]})"
p4rt-ctl add-entry br0 linux_networking_control.rx_phy_port_to_pr_map "vmeta.common.port_id={vf_list[i]},zero_padding=0,action=linux_networking_control.fwd_to_vsi({acc_pr['port']})"
p4rt-ctl add-entry br0 linux_networking_control.source_port_to_pr_map "user_meta.cmeta.source_port={vf_list[i]},zero_padding=0,action=linux_networking_control.fwd_to_vsi({acc_pr['port']})"
p4rt-ctl add-entry br0 linux_networking_control.tx_acc_vsi "vmeta.common.vsi={acc_pr['vsi_num']},zero_padding=0,action=linux_networking_control.l2_fwd_and_bypass_bridge({vf_list[i]})"
sleep 2

"""

            ovs_vxlan += f"""echo ""
echo "IPU Port {vf_list[i]} mapped to ACC Port {acc_pr_list[i]} MAC ({acc_pr['mac']})  VSI ({acc_pr['vsi_id']}:{acc_pr['vsi_num']}:{acc_pr['port']})"
echo "ACC Port {acc_pr_list[i]} is added to OVS bridge br-tun-{vf_list[i]}"
ovs-vsctl del-br br-tun-{vf_list[i]}
ovs-vsctl add-br br-tun-{vf_list[i]}
ovs-vsctl add-port br-tun-{vf_list[i]} {acc_pr_list[i]}
"""
        else:
            vf = test_setup.get_interface_info(server_name='host', interface_name=vf_list[i])
            acc_pr = test_setup.get_interface_info(server_name='acc', interface_name=acc_pr_list[i])
            vf_to_acc += f"""echo ""
echo "Host IDPF Interface {vf_list[i]} MAC ({vf['mac']})  VSI ({vf['vsi_id']}:{vf['vsi_num']})  PORT ({vf['port']}) maps to"
echo "ACC  IDPF Interface {acc_pr_list[i]} MAC ({acc_pr['mac']})  VSI ({acc_pr['vsi_id']}:{acc_pr['vsi_num']})  PORT ({acc_pr['port']})"
p4rt-ctl add-entry br0 linux_networking_control.tx_source_port "vmeta.common.vsi={vf['vsi_num']}/2047,priority=1,action=linux_networking_control.set_source_port({vf['port']})"
p4rt-ctl add-entry br0 linux_networking_control.source_port_to_pr_map "user_meta.cmeta.source_port={vf['port']},zero_padding=0,action=linux_networking_control.fwd_to_vsi({acc_pr['port']})"
p4rt-ctl add-entry br0 linux_networking_control.tx_acc_vsi "vmeta.common.vsi={acc_pr['vsi_num']},zero_padding=0,action=linux_networking_control.l2_fwd_and_bypass_bridge({vf['port']})"
p4rt-ctl add-entry br0 linux_networking_control.vsi_to_vsi_loopback "vmeta.common.vsi={acc_pr['vsi_num']},target_vsi={vf['vsi_num']},action=linux_networking_control.fwd_to_vsi({vf['port']})"
p4rt-ctl add-entry br0 linux_networking_control.vsi_to_vsi_loopback "vmeta.common.vsi={vf['vsi_num']},target_vsi={acc_pr['vsi_num']},action=linux_networking_control.fwd_to_vsi({acc_pr['port']})"
sleep 2

"""
            print("i {}".format(i))
            if i <= vf_list_len-2:
                print("vm id {}".format(vm_id))
                ovs_vxlan += f"""echo ""
echo "Host IDPF Interface {vf_list[i]} MAC ({vf['mac']})  VSI ({vf['vsi_id']}:{vf['vsi_num']}:{vf['port']}) maps to"
echo "ACC Port {acc_pr_list[i]} MAC ({acc_pr['mac']})  VSI ({acc_pr['vsi_id']}:{acc_pr['vsi_num']}:{acc_pr['port']})"
echo "ACC Port {acc_pr_list[i]} is added to OVS bridge br{vm_id}"
ip link del TEP{vm_id}
ovs-vsctl del-br br-int-{vm_id}
ip link add dev TEP{vm_id} type dummy
ovs-vsctl add-br br-int-{vm_id}
ovs-vsctl add-port br-int-{vm_id} {acc_pr_list[i]}
ovs-vsctl add-port br-int-{vm_id} {acc_pr_list[vf_list_len-1]}
ifconfig TEP{vm_id} {local_vtep[vm_id]}/24 up
ovs-vsctl add-port br-int-{vm_id} vxlan{vm_id} -- set interface vxlan{vm_id} type=vxlan options:local_ip={local_vtep[vm_id]} options:remote_ip={remote_vtep[vm_id]} options:key=1{vm_id} options:dst_port=4789
ifconfig br-int-{vm_id} up
"""


            vf_to_vm += f'''
echo ""
nmcli device set {vf_list[i]}  managed no
ip addr add {vm_ip_list[vm_id]}/24 dev {vf_list[i]}
ifconfig {vf_list[i]} up
sleep 2

'''

            vm_id += 1

        mac_list.append(str(acc_pr['mac']))


    misc = """p4rt-ctl add-entry br0 linux_networking_control.ipv4_lpm_root_lut "user_meta.cmeta.bit16_zeros=4/65535,priority=2048,action=linux_networking_control.ipv4_lpm_root_lut_action(0)"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=0/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=1/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=2/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=3/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=4/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=5/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=6/7,priority=1,action=linux_networking_control.bypass"
p4rt-ctl add-entry br0 linux_networking_control.tx_lag_table "user_meta.cmeta.lag_group_id=0/255,hash=7/7,priority=1,action=linux_networking_control.bypass"
"""

    acc_path = test_setup.test_config['test_params']['acc_path']
    acc_p4_path = f'{acc_path}/fxp-net_linux-networking'
    file = f'{path}/es2k_skip_p4.conf'
    p4_config = 'cat <<EOF > ./'+file+'''
{
    "chip_list": [
        {
            "id": "asic-0",
            "chip_family": "mev",
            "instance": 0,
            "pcie_bdf": "0000:00:01.6",
            "iommu_grp_num": 7,
            "ctrl_map" : ["NETDEV","''' + '","'.join(mac_list) + '''" ,1]
        }
    ],
    "instance": 0,
    "cfgqs-idx": "0-15",
    "p4_devices": [
        {
            "device-id": 0,
            "fixed_functions" : [
                {
                    "name": "crypto",
                    "tdi": "/opt/p4/p4sde/share/mev_reference_sample_files/fixed_function/crypto_mgr/ipsec_sad_offload.json",
                    "ctx": "/opt/p4/p4sde/share/mev_reference_sample_files/fixed_function/crypto_mgr/ipsec_sad_offload_ctx.json"
                }
            ],
            "eal-args": "--lcores=1-2 -a 00:01.6,vport=[0-1] -- -i --rxq=1 --txq=1 --hairpinq=1 --hairpin-mode=0x0",
            "p4_programs": [
                {
                    "program-name": "fxp-net_linux-networking",
                    "tdi-config": "'''+acc_p4_path+'''/tdi.json",
                    "p4_pipelines": [
                        {
                            "p4_pipeline_name": "main",
                            "context": "'''+acc_p4_path+'''/context.json",
                            "config": "'''+acc_p4_path+'''/ipu.bin",
                            "pipe_scope": [
                                0,
                                1,
                                2,
                                3
                            ],
                            "path": "'''+acc_p4_path+'''/"
                        }
                    ]
                }
            ],
            "agent0": "lib/libpltfm_mgr.so"
        }
    ]
}
EOF
'''
    command_list.append(p4_config)

    command_list.append(host_idpf)
    command_list.append(host_comm_channel)

    file = f'{path}/setup_acc_comm_channel.sh'
    host_acc_comm_channel = 'cat <<EOF > ./'+file+'''
#!/bin/sh
#Assign IP in ACC for Host - ACC comm channel
nmcli device set enp0s1f0d3 managed no
ip addr add '''+comm_ip_acc+'''/24 dev enp0s1f0d3
ip link set up dev enp0s1f0d3

#Untar P4 tarball
tar -xzvf /opt/p4.tar.gz -C /opt/
EOF
'''
    command_list.append(host_acc_comm_channel)


    file = f'{path}/sync_host_acc_date.sh'
    sync_host_acc_date = 'cat <<EOF > ./'+file+'''
#!/bin/sh
# Sync Date from host to acc
timezonestr=\\$(timedatectl show| grep Timezone)
timezone=\\$(echo "\\$timezonestr" | cut -d'=' -f2)
hostdate=\\$(date)

echo \\$timezonestr
echo \\$timezone
echo \\$hostdate
ssh -o LogLevel=quiet  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@'''+comm_ip_acc+''' "timedatectl set-timezone \"\\$timezone\""
ssh -o LogLevel=quiet  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@'''+comm_ip_acc+''' "date -s \'\\${hostdate}\'"

EOF
'''
    command_list.append(sync_host_acc_date)




    file = f'{path}/generate_certs.sh'
    generate_certs = 'cat <<EOF > ./'+file+'''
#!/bin/sh

#Generate Certs
echo ""
echo "Generate the TLS Certs for Infrap4d"
cd /usr/share/stratum/
COMMON_NAME='''+comm_ip_acc+''' ./generate-certs.sh
sleep 10

EOF
'''
    command_list.append(generate_certs)



    file = f'{path}/copy_certs.sh'
    copy_certs = 'cat <<EOF > ./'+file+'''
#!/bin/sh
#Copy certs
echo ""
echo "Copy the certs from ACC to host"
mkdir -p /usr/share/stratum/
cd /usr/share/stratum/
scp -r -o LogLevel=quiet  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    root@'''+comm_ip_acc+''':/usr/share/stratum/certs /usr/share/stratum
EOF
'''
    command_list.append(copy_certs)



    file = f'{path}/2_acc_infrap4d.sh'
    acc_infrap4d = 'cat <<EOF > ./'+file+'''
#!/bin/sh
#ACC Environment for Infrap4d:
echo ""
echo "Setup the environment in ACC to run Infrap4d"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export no_proxy=localhost,127.0.0.1,192.168.0.0/16
export NO_PROXY=localhost,127.0.0.1,192.168.0.0/16
unset http_proxy
unset https_proxy

export OUTPUT_DIR='''+acc_p4_path+'''



echo ""
echo "Copy Infrap4d Config file es2k_skip_p4.conf to /usr/share/stratum/es2k/es2k_skip_p4.conf"
touch \$OUTPUT_DIR/ipu.bin
yes | cp -f \$OUTPUT_DIR/es2k_skip_p4.conf /usr/share/stratum/es2k/es2k_skip_p4.conf


echo ""
echo "Load the vfio-pci driver to bind the vfio-pci 00:01.6"
sudo modprobe vfio-pci
sudo /opt/p4/p4sde/bin/dpdk-devbind.py -b vfio-pci 00:01.6

echo ""
echo "Set hugepages"
sudo /opt/p4/p4sde/bin/dpdk-hugepages.py -p 2M -r 2G

echo ""
echo "stop firewall"
systemctl stop firewalld


echo ""
echo "Verify the infrap4d config"
cat /usr/share/stratum/es2k/es2k_skip_p4.conf



echo ""
echo "Start Infrap4d"
#Start Infrap4d
/opt/p4/p4-cp-nws/sbin/infrap4d --local_stratum_url="'''+comm_ip_acc+''':9339" --external_stratum_urls="'''+comm_ip_acc+''':9339,'''+comm_ip_acc+''':9559"
EOF
'''

    command_list.append(acc_infrap4d)

    file = f'{path}/3_acc_p4rt.sh'
    acc_p4rt = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo "Setup P4 Runtime Pipeline"
echo "P4 Artifacts are in Folder : OUTPUT_DIR='''+acc_p4_path+'''"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin

tdi_pipeline_builder --p4c_conf_file=/usr/share/stratum/es2k/es2k_skip_p4.conf --tdi_pipeline_config_binary_file=\$OUTPUT_DIR/fxp-net_linux-networking.pb.bin

alias p4rt-ctl='p4rt-ctl -g  '''+comm_ip_acc+''':9559 '

sleep 2
echo ""
echo "Use p4rt-ctl set-pipe to setup the runtime pipeline"
p4rt-ctl set-pipe br0 \$OUTPUT_DIR/fxp-net_linux-networking.pb.bin \$OUTPUT_DIR/p4Info.txt -g '''+comm_ip_acc+''':9559
#to do check for comm ip
sleep 2
echo ""
echo "Get IDPF Interface MAC and VSI info from IMC command : cli_client -q -c"
echo "VSI (hexadecimal:decimal) PORT (VSI+16)"
echo "Use p4rt-ctl to configure the VFs -- ACC PR"
'''+vf_to_acc+'''
sleep 2
echo ""
echo "Use p4rt-ctl to configure the Physical Ports -- ACC PR"
'''+phy_to_acc+'''
sleep 2
echo ""
echo "Configure supporting p4 runtime tables for LPM and LAG bypass"
'''+misc+'''
EOF
'''
    command_list.append(acc_p4rt)

    file = f'{path}/acc_p4rt_delete.sh'
    acc_p4rt_delete = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo "Delete the P4 Runtime Rules"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
alias p4rt-ctl='p4rt-ctl -g  '''+comm_ip_acc+''':9559 '


echo "Use p4rt-ctl to remove the rules for the VFs -- ACC PR"
'''+vf_to_acc+'''
sleep 2
echo ""
echo "Use p4rt-ctl to remove the rules for Physical Ports -- ACC PR"
'''+phy_to_acc+'''
sleep 2
echo ""
echo "Remove supporting p4 runtime tables for LPM and LAG bypass"
'''+misc+'''
EOF
'''
    command_list.append(acc_p4rt_delete)

    delete_command = f'''
sed -i 's/add-entry/del-entry/g' {file}
sed -i 's/,action.*"/"/g' {file}
'''
    command_list.append(delete_command)

    file = f'{path}/4_acc_p4rt_dump.sh'
    acc_p4rt_dump = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo "Setup P4 Runtime Pipeline"
echo "P4 Artifacts are in Folder : OUTPUT_DIR='''+acc_p4_path+'''"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
alias p4rt-ctl='p4rt-ctl -g  '''+comm_ip_acc+''':9559 '

echo ""
echo "p4rt-ctl dump-entries br0 linux_networking_control.rx_source_port "
p4rt-ctl dump-entries br0

EOF
'''

    command_list.append(acc_p4rt_dump)
    file = f'{path}/5_acc_setup_ovs.sh'
    acc_setup_ovs = 'cat <<EOF > ./'+file+'''
#!/bin/sh

killall ovsdb-server
killall ovs-vswitchd

echo ""
echo "Setup the Environment to run OVS"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
export RUN_OVS=/opt/p4/p4-cp-nws

rm -rf \$RUN_OVS/etc/openvswitch
rm -rf \$RUN_OVS/var/run/openvswitch
mkdir -p \$RUN_OVS/etc/openvswitch/
mkdir -p \$RUN_OVS/var/run/openvswitch

ovsdb-tool create \$RUN_OVS/etc/openvswitch/conf.db \$RUN_OVS/share/openvswitch/vswitch.ovsschema

echo ""
echo "Start the ovsdb-server"
ovsdb-server --remote=punix:\$RUN_OVS/var/run/openvswitch/db.sock --remote=db:Open_vSwitch,Open_vSwitch,manager_options --pidfile --detach

ovs-vsctl --no-wait init

echo ""
echo "Start the ovs-vswitchd"
mkdir -p /tmp/logs
ovs-vswitchd --pidfile --detach --mlockall --log-file=/tmp/logs/ovs-vswitchd.log  --grpc-addr="'''+comm_ip_acc+'''"

ovs-vsctl set Open_vSwitch . other_config:n-revalidator-threads=1
ovs-vsctl set Open_vSwitch . other_config:n-handler-threads=1
echo ""
echo "Verify OVS: ovsdb-server and ovs-vswitchd are running"
ovs-vsctl  show

ps -aux | grep ovs
EOF
'''
    command_list.append(acc_setup_ovs)
    file = f'{path}/6_acc_ovs_bridge.sh'
    acc_ovs_bridge = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo "Setup the Environment to run OVS"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
export RUN_OVS=/opt/p4/p4-cp-nws

echo ""
echo "Setup an OVS Bridge br-intrnl"
ovs-vsctl del-br br-intrnl
ovs-vsctl add-br br-intrnl
ovs-vsctl add-port br-intrnl enp0s1f0d4
ovs-vsctl add-port br-intrnl enp0s1f0d6
ovs-vsctl add-port br-intrnl vxlan1 -- set interface vxlan1 type=vxlan \
    options:local_ip=10.1.1.1 options:remote_ip=10.1.1.2 options:key=10 options:dst_port=4789
ifconfig br-intrnl up

# setup br-tunl
ovs-vsctl del-br br-tunl
ovs-vsctl add-br br-tunl
ovs-vsctl add-port br-tunl enp0s1f0d5
ifconfig br-tunl 1.1.1.1/24 up

ip link add dev TEP10 type dummy
ifconfig TEP10 10.1.1.1/24 up
ip route change 10.1.1.0/24 via 1.1.1.2 dev br-tunl

sleep 2
ovs-vsctl show

echo "Check the interface configuration"
sleep 1
ip -br a

EOF
'''
    command_list.append(acc_ovs_bridge)


    file = f'{path}/proxy.sh'
    proxy_setup = 'cat <<EOF > ./'+file+'''
#!/bin/sh
export no_proxy=$no_proxy,'''+comm_ip_acc+'''/16
export NO_PROXY=$no_proxy
unset http_proxy
unset https_proxy
EOF
'''
    command_list.append(proxy_setup)


    file = f'{path}/host_ipsec_config.sh'
    host_ipsec_config = 'cat <<EOF > ./'+file+'''
#!/bin/sh
echo "Setup the Host IPsec config"

echo "Copying the p4info and binaries to host"
scp -o LogLevel=quiet  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@'''+comm_ip_acc+''':'''+acc_p4_path+'''/p4Info.txt /var/tmp/linux_networking.p4info.txt
scp -o LogLevel=quiet  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@'''+comm_ip_acc+''':'''+acc_p4_path+'''/fxp-net_linux-networking.pb.bin /var/tmp/ipsec_fixed_func.pb.bin


echo "Stop firewall"
systemctl stop firewalld


sed -i 's/gnmi_server=.*/gnmi_server='''+comm_ip_acc+''':9339/g' '''+strongSwan_build+'''/ipsec_offload_plugin/ipsec_offload.conf
sed -i 's/p4rt_server=.*/p4rt_server='''+comm_ip_acc+''':9559/g' '''+strongSwan_build+'''/ipsec_offload_plugin/ipsec_offload.conf
yes | cp -f '''+strongSwan_build+'''/ipsec_offload_plugin/ipsec_offload.conf /usr/share/stratum


EOF
'''
    command_list.append(host_ipsec_config)


    file = f'{path}/ipsec.conf_transport_1'
    create_ipsec_conf_transport_1 = 'cat <<EOF > ./'+file+'''
conn sts-base
    fragmentation=yes
    keyingtries=%forever
    ike=aes256-sha1-modp1024,3des-sha1-modp1024!
    esp=aes256gcm128
    leftauth=psk
    rightauth=psk
    keyexchange=ikev2
    #replay_window=32
    #rekey=yes
    rekey=no
    lifebytes=1000000000000000000
    marginbytes=500000000000000000
    type=transport
    leftprotoport=tcp
    rightprotoport=tcp
    auto=start
    left=192.168.1.101
    right=192.168.1.102
    leftid=192.168.1.101
    rightid=192.168.1.102
EOF
'''
    command_list.append(create_ipsec_conf_transport_1)


    file = f'{path}/ipsec.conf_tunnel_1'
    create_ipsec_conf_tunnel_1 = 'cat <<EOF > ./'+file+'''
conn sts-base
        fragmentation=yes
        keyingtries=%forever
        ike=aes256-sha1-modp1024,3des-sha1-modp1024!
        esp=aes256gcm128
        leftauth=psk
        rightauth=psk
        keyexchange=ikev2
        #replay_window=32
        #lifetime=1
        #margintime=30m
        #rekey=yes
        lifebytes=100000000000
        marginbytes=6000000000
        rekey=no
        type=tunnel
        leftprotoport=tcp
        rightprotoport=tcp
        left=192.168.1.101
        right=192.168.1.102
        leftid=192.168.1.101
        rightid=192.168.1.102
        leftsubnet=11.0.0.1
        rightsubnet=11.0.0.2
        auto=start
EOF
'''
    command_list.append(create_ipsec_conf_tunnel_1)


    file = f'{path}/ipsec.conf_transport_2'
    create_ipsec_conf_transport_2 = 'cat <<EOF > ./'+file+'''
conn sts-base
    fragmentation=yes
    keyingtries=%forever
    ike=aes256-sha1-modp1024,3des-sha1-modp1024!
    esp=aes256gcm128
    leftauth=psk
    rightauth=psk
    keyexchange=ikev2
    #replay_window=32
    #rekey=yes
    rekey=no
    lifebytes=1000000000000000000
    marginbytes=500000000000000000
    type=transport
    leftprotoport=tcp
    rightprotoport=tcp
    auto=add
    left=192.168.1.102
    right=192.168.1.101
    leftid=192.168.1.102
    rightid=192.168.1.101
EOF
'''
    command_list.append(create_ipsec_conf_transport_2)


    file = f'{path}/ipsec.conf_tunnel_2'
    create_ipsec_conf_tunnel_2 = 'cat <<EOF > ./'+file+'''
conn sts-base
        fragmentation=yes
        keyingtries=%forever
        ike=aes256-sha1-modp1024,3des-sha1-modp1024!
        esp=aes256gcm128
        leftauth=psk
        rightauth=psk
        keyexchange=ikev2
        #replay_window=32
        #lifetime=1
        #margintime=30m
        #rekey=yes
        lifebytes=100000000000
        marginbytes=6000000000
        rekey=no
        type=tunnel
        leftprotoport=tcp
        rightprotoport=tcp
        left=192.168.1.102
        right=192.168.1.101
        leftid=192.168.1.102
        rightid=192.168.1.101
        leftsubnet=11.0.0.2
        rightsubnet=11.0.0.1
        auto=add
EOF
'''
    command_list.append(create_ipsec_conf_tunnel_2)



    local_vxlan_tunnel_mac_len = len(local_vxlan_tunnel_mac)
    ipsec_tunnel_local_mac = ''

    for i in range(local_vxlan_tunnel_mac_len):
        first_octet, second_octet, third_octet = split_mac(local_vxlan_tunnel_mac[i])
        ipsec_tunnel_local_mac += f"""echo ""
# HOST_VF_INTF
# ens801f0v0 : 00:1c:00:00:03:14 <-- 192.168.1.101 MAC address
p4rt-ctl add-entry br0 linux_networking_control.rif_mod_table_start \
    "rif_mod_map_id0=0x0005,action=linux_networking_control.set_src_mac_start(arg=0x{first_octet})"
p4rt-ctl add-entry br0 linux_networking_control.rif_mod_table_mid \
    "rif_mod_map_id1=0x0005,action=linux_networking_control.set_src_mac_mid(arg=0x{second_octet})"
p4rt-ctl add-entry br0 linux_networking_control.rif_mod_table_last \
    "rif_mod_map_id2=0x0005,action=linux_networking_control.set_src_mac_last(arg=0x{third_octet})"

"""


    remote_vxlan_mac_len = len(remote_vxlan_mac)
    ipsec_tunnel_remote_vxlan_mac = ''
    for i in range(remote_vxlan_mac_len):
        first_split, second_split = split_mac_2(remote_vxlan_mac[i])

        ipsec_tunnel_remote_vxlan_mac += f"""echo ""
# CVL_HOST - nexthop - use remote host's MAC
# vxlan10  : ee:35:eb:f9:2f:2b <-- tunnel MAC 192.168.1.102 on remote host
p4rt-ctl add-entry br0 linux_networking_control.nexthop_table \
    "user_meta.cmeta.nexthop_id=4,bit16_zeros=0,action=linux_networking_control.set_nexthop_info_dmac(router_interface_id=0x5,egress_port=0,dmac_high=0x{first_split},dmac_low=0x{second_split})"
"""


    remote_vxlan_ip_len = len(remote_vxlan_ip)
    ipsec_tunnel_remote_vxlan_ip = ''
    for i in range(remote_vxlan_ip_len):
        hex_ip = ip_dec_to_hex(remote_vxlan_ip[i])

        ipsec_tunnel_remote_vxlan_ip += f"""echo ""
# Add to ipv4_table <-- entry for IPsec tunnel routing lookup
# 0xc0a80166 = 192.168.1.102 (remote vxlan tunnel IP)
p4rt-ctl add-entry br0 linux_networking_control.ipv4_table \
    "ipv4_table_lpm_root=0,ipv4_dst_match=0x{hex_ip}/24,action=linux_networking_control.ipv4_set_nexthop_id(nexthop_id=0x4)"

"""


    file = f'{path}/ipsec_tunnel_config.sh'
    ipsec_tunnel_config = 'cat <<EOF > ./'+file+'''
#!/bin/sh

export PATH=/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin:$PATH
export SDE_INSTALL=/opt/p4/p4sde
export LD_LIBRARY_PATH=/opt/p4/p4-cp-nws/lib:/opt/p4/p4-cp-nws/lib64:$SDE_INSTALL/lib64:$SDE_INSTALL/lib:/usr/lib64:/usr/lib:/usr/local/lib64:/usr/local/lib
export P4CP_INSTALL=/opt/p4/p4-cp-nws

alias p4rt-ctl='p4rt-ctl -g  '''+comm_ip_acc+''':9559 '
echo "Setup the Host VMs and VFs"


'''+ipsec_tunnel_local_mac+'''

'''+ipsec_tunnel_remote_vxlan_mac+'''

'''+ipsec_tunnel_remote_vxlan_ip+'''


EOF
'''
    command_list.append(ipsec_tunnel_config)


    file = f'{path}/ipsec.secrets'
    ipsec_secrets = 'cat <<EOF > ./'+file+'''
# ipsec.secrets - strongSwan IPsec secrets file
   : PSK "example"
EOF
'''
    command_list.append(ipsec_secrets)

    file = f'{path}/acc_ovs_vxlan.sh'
    acc_ovs_vxlan = 'cat <<EOF > ./'+file+'''
#!/bin/sh

echo "Setup the Environment to run OVS"
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=\$P4CP_INSTALL
export OUTPUT_DIR='''+acc_p4_path+'''
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
export RUN_OVS=/opt/p4/p4-cp-nws


'''+ovs_vxlan+'''
ifconfig br-tun-0 '''+local_br_tun[0]+'''/24 up
ip route change 10.1.1.0/24 via '''+remote_br_tun[0]+''' dev br-tun-0

sleep 2
ovs-vsctl show

echo "Check the interface configuration"
sleep 1
ip -br a

EOF
'''
    command_list.append(acc_ovs_vxlan)


    file = f'{path}/7_host_vm.sh'
    host_vm = 'cat <<EOF > ./'+file+'''
#!/bin/sh
echo "Configure the Host VF Interfaces"

'''+vf_to_vm+'''

EOF
'''
    command_list.append(host_vm)


    set_intf_mtu = ''
    vf_list_len = len(vf_list)
    for i in range(vf_list_len):
        if str(vf_list[i]) != '0' and str(vf_list[i]) != '1':
            set_intf_mtu += f"""echo ""
ifconfig {vf_list[i]} mtu 4096
sleep 2
"""

    tune_intf = ''
    vf_list_len = len(vf_list)
    for i in range(vf_list_len):
        if str(vf_list[i]) != '0' and str(vf_list[i]) != '1':
            tune_intf += f"""echo ""
{ipu_sdk_path}/common/drivers/idpf/src/COMMON/scripts/set_irq_affinity local {vf_list[i]}
sleep 5
"""

    file = f'{path}/perf_tune.sh'
    perf_tune = 'cat <<EOF > ./'+file+'''
#!/bin/sh

#Change the MTU to 4096

'''+set_intf_mtu+'''

#Disable irq
echo "stopping irqbalance"
systemctl stop irqbalance.service
sleep 1
systemctl status irqbalance.service

'''+tune_intf+'''

EOF
'''
    command_list.append(perf_tune)


    command_list.append(f"chmod +x {path}/*")

    for command in command_list:
        try:
            result = test_setup.ssh_command('host', command)
        except Exception as e:
            print(f"Failed with exception:\n{e}")

    return None


def build_args():
    # Create the top-level parser
    parser = argparse.ArgumentParser(description='Run Linux networking with IPsec Acceleration')
    subparsers = parser.add_subparsers(dest='command', help='options')
    # Create the parser for the "load_package" command and add subparser for linux_networking and default mode
    parser_load_package = subparsers.add_parser('load_package', help='Update the P4 package on the IMC and reboot IMC')
    load_package_subparsers = parser_load_package.add_subparsers(dest='mode')
    # Create the subparser for the "load_package" command for linux networking
    load_package_subparsers.add_parser('linux_networking', help='load p4 package fxp-net_linux-networking.pkg and perform IMC reboot')
    # Create the subparser for the "load_package" command for default package
    load_package_subparsers.add_parser('default', help='Revert to the default P4 package e2100-default-<version>.pkg and perform IMC reboot')
    # Create the parser for the "setup" command
    parser_setup = subparsers.add_parser('setup', help='Setup the complete OVS offload Recipe')
    # Create the parser for the "ipsec_transport" command
    parser_setup = subparsers.add_parser('ipsec_transport', help='Setup the IPsec configs for transport mode')
    # Create the parser for the "ipsec_tunnel" command
    parser_setup = subparsers.add_parser('ipsec_tunnel', help='Setup the IPsec configs for tunnel mode')
    # Create the parser for the "ipsec_performance" command
    parser_setup = subparsers.add_parser('ipsec_performance', help='Tune for performance')
    # Create the parser for the "teardown" command
    parser_teardown = subparsers.add_parser('teardown', help='Teardown the IPsec offload Recipe')
    # Create the parser for the "create_script" command
    parser_create_script = subparsers.add_parser('create_script', help='Generate configuration scripts in localhost')
    # Create the parser for the "copy_script" command
    parser_copy_script = subparsers.add_parser('copy_script', help='Copy configuration scripts to IMC and ACC')
    return parser, parser_load_package


if __name__ == "__main__":
    test_setup = TestSetup(config_file = f'{os.path.dirname(os.path.abspath(__file__))}/config.yaml')
    host_path = test_setup.test_config['test_params']['host_path']
    imc_path = test_setup.test_config['test_params']['imc_path']
    acc_path = test_setup.test_config['test_params']['acc_path']
    ip_list = test_setup.test_config['test_params']['ip_list']
    imc_ip = test_setup.test_config['imc']['ssh']['ip']
    acc_ip = test_setup.test_config['acc']['ssh']['ip']
    acc_p4_path = f'{acc_path}/fxp-net_linux-networking'
    host_password = test_setup.test_config['host']['ssh']['password']
    imc_login = f'ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@{imc_ip}'
    acc_login = f'ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@{acc_ip}'
    strongSwan_build = test_setup.test_config['test_params']['strongSwan_build']
    ipsec_host = test_setup.test_config['test_params']['ipsec_host']

    parser, parser_load_package = build_args()
    # Parse the arguments
    args = parser.parse_args()

    # Execute the appropriate function based on the subcommand
    if args.command == 'load_package':
         if args.mode is None:
             parser_load_package.print_help()
             sys.exit()

         if args.mode == 'linux_networking':
             print("\n----------------Load the P4 package fxp-net_linux-networking.pkg on IMC and reboot IPU----------------")
             test_setup.load_custom_package(p4='fxp-net_linux-networking')

         if args.mode == 'default':
             print("\n----------------Revert to Default P4 package e2100-default-<version>.pkg on IMC and reboot IPU----------------")
             test_setup.load_custom_package(p4='default')

    elif args.command == 'setup':

        if len(host_password) == 0:
            print("Enter correct IPU Host SSH root password in config.yaml and retry")
            sys.exit()

        print("\n----------------Create IPsec Offload scripts----------------")
        build_p4rt_config(test_setup = test_setup)
        print("\n----------------Copy IPsec Offload scripts to the ACC----------------")
        test_setup.copy_scripts()

        print("\n----------------Setup Linux Networking for IPsec Offload----------------")

        # Setup a TMUX session, for host comm channel
        print("\n----------------Setup TMUX Session and Login to the Host----------------")
        host_comm = tmux_term(test_setup=test_setup, tmux_name="test_host_comm",tmux_override=True)
        cwd = os.getcwd()
        print("cwd  {}".format(cwd))
        result = host_comm.tmux_send_keys('sudo -s', delay=2, output=True)
        result = host_comm.tmux_send_keys(f'{host_password}', delay=2, output=True)
        result = host_comm.tmux_send_keys(f'cd {cwd}/{host_path}', delay=2, output=True)

        print("\n----------------Configure host comm channel for Host - ACC Communication----------------")
        result = host_comm.tmux_send_keys('ls -lrt', delay=2, output=True)
        print(f'{result}')
        result = host_comm.tmux_send_keys('./setup_host_comm_channel.sh', delay=10, output=True)
        print(result)


        # Setup a TMUX session, Login to ACC and configure ACC comm channel for Host - ACC Communication
        print("\n----------------Setup TMUX Session, Login to ACC----------------")
        acc_comm = tmux_term(test_setup=test_setup, tmux_name="test_acc_comm",tmux_override=True)
        result = acc_comm.tmux_send_keys(imc_login, delay=2, output=True)
        result = acc_comm.tmux_send_keys(acc_login, delay=2, output=True)
        result = acc_comm.tmux_send_keys(f'cd {acc_path}/{host_path}', delay=2, output=True)
        result = acc_comm.tmux_send_keys('ls -lrt', delay=2, output=True)


        print("\n----------------Configure ACC for Host - ACC communication----------------")
        result = acc_comm.tmux_send_keys('./setup_acc_comm_channel.sh', delay=90, output=True)
        print(result)


        # Sync date between Host and ACC
        print("\n----------------Sync date between host and ACC----------------")
        print("cwd  {}".format(cwd))
        result = host_comm.tmux_send_keys('./sync_host_acc_date.sh', delay=60, output=True)
        print(result)


       # Genereate certs
        print("\n----------------Generate certs ----------------")
        result = acc_comm.tmux_send_keys(f'cd {acc_path}/{host_path}', delay=2, output=True)
        result = acc_comm.tmux_send_keys('ls -lrt', delay=2, output=True)
        result = acc_comm.tmux_send_keys('./generate_certs.sh', delay=60, output=True)
        print(result)


        # Copy certs to host from ACC
        print("\n----------------Copy certs from ACC to Host----------------")
        result = host_comm.tmux_send_keys('./copy_certs.sh', delay=15, output=True)
        print(result)

        # Setup a TMUX session, Login to ACC and start infrap4d
        print("\n----------------Setup TMUX Session, Login to ACC----------------")
        infrap4d = tmux_term(test_setup=test_setup, tmux_name="test_infrap4d",tmux_override=True)
        result = infrap4d.tmux_send_keys(imc_login, delay=2, output=True)
        result = infrap4d.tmux_send_keys(acc_login, delay=2, output=True)


        print("\n----------------Copy Infrap4d Configuration file----------------")
        result = infrap4d.tmux_send_keys(f'yes | cp -f {acc_path}/{host_path}/es2k_skip_p4.conf {acc_path}/fxp-net_linux-networking/', delay=2, output=True)
        print(result)
        result = infrap4d.tmux_send_keys(f'cd {acc_path}/{host_path}', delay=2, output=True)
        result = infrap4d.tmux_send_keys('ls -lrt', delay=2, output=True)

        print("\n----------------Start Infrap4d, wait for initialization to complete----------------")
        time.sleep(15)
        result = infrap4d.tmux_send_keys('./2_acc_infrap4d.sh', delay=180, output=True)
        print(result)

        # Setup a TMUX session, Login to ACC, configure p4rt rules and ovs bridges
        print("\n----------------Setup TMUX Session, Login to ACC----------------")
        p4rt = tmux_term(test_setup=test_setup, tmux_name="test_p4rt",tmux_override=True)
        result = p4rt.tmux_send_keys(imc_login, delay=2)
        result = p4rt.tmux_send_keys(acc_login, delay=2)
        result = p4rt.tmux_send_keys(f'cd {acc_path}/{host_path}', delay=2, output=True)

        print("\n----------------Use p4rt-ctl to Add the rules----------------")
        result = p4rt.tmux_send_keys('./3_acc_p4rt.sh', delay=60, output=True)
        print(result)
        print("\n----------------Use p4rt-ctl to Dump the rules----------------")
        result = p4rt.tmux_send_keys('./4_acc_p4rt_dump.sh', delay=20, output=True)
        print(result)

        print("\n----------------Setup OVS Environment on the ACC----------------")
        result = p4rt.tmux_send_keys('./5_acc_setup_ovs.sh', delay=10, output=True)
        print(result)
        print("\n----------------Configure OVS Bridges----------------")
        result = p4rt.tmux_send_keys('./acc_ovs_vxlan.sh', delay=10, output=True)
        print(result)

        # Setup a TMUX session for the IPU host, configure the VMs, idpf interfaces, Link partner interfaces and run ping checks
        print("\n----------------Setup TMUX Session and Login to the Host----------------")
        host = tmux_term(test_setup=test_setup, tmux_name="test3_host",tmux_override=True)
        result = host.tmux_send_keys(f'cd {host_path}', delay=2, output=True)
        result = host.tmux_send_keys('sudo -s', delay=2, output=True)
        result = host.tmux_send_keys(f'{host_password}', delay=2, output=True)

        print("\n----------------Configure the VMs on the Host and ADD the IDPF SR-IOV VFs----------------")
        result = host.tmux_send_keys('ls -lrt', delay=2, output=True)
        print(f'{result}')
        result = host.tmux_send_keys('./7_host_vm.sh', delay=10, output=True)
        print(result)


    elif args.command == 'ipsec_transport':
        host_ipsec = tmux_term(test_setup=test_setup, tmux_name="test_host_ipsec",tmux_override=True)
        print("\n----------------Configure IPsec environment on the host----------------")
        result = host_ipsec.tmux_send_keys(f'cd {host_path}', delay=2, output=True)
        result = host_ipsec.tmux_send_keys('./host_ipsec_config.sh', delay=15, output=True)
        print(result)
        result = host_ipsec.tmux_send_keys('source proxy.sh', delay=10, output=True)
        result = host_ipsec.tmux_send_keys(f'yes|cp -f ipsec.secrets {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/', delay=2, output=True)
        if ipsec_host == '1':
            result = host_ipsec.tmux_send_keys(f'yes|cp -f ipsec.conf_transport_1 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf', delay=2, output=True)

        elif ipsec_host == '2':
            result = host_ipsec.tmux_send_keys(f'yes|cp -f ipsec.conf_transport_2 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf', delay=2, output=True)

        result = host_ipsec.tmux_send_keys(f'cd {strongSwan_build}', delay=2, output=True)
        result = host_ipsec.tmux_send_keys('source env_setup_acc.sh', delay=15, output=True)
        result = host_ipsec.tmux_send_keys(f'cd {strongSwan_build}//ipsec_offload_plugin/output_strongswan/usr/sbin', delay=2, output=True)

    elif args.command == 'ipsec_tunnel':
        host_ipsec = tmux_term(test_setup=test_setup, tmux_name="test_host_ipsec",tmux_override=True)
        print("\n----------------Configuration for tunnel mode----------------")
        p4rt = tmux_term(test_setup=test_setup, tmux_name="test_p4rt",tmux_override=True)
        result = p4rt.tmux_send_keys(imc_login, delay=2)
        result = p4rt.tmux_send_keys(acc_login, delay=2)
        result = p4rt.tmux_send_keys(f'cd {acc_path}/{host_path}', delay=2, output=True)

        result = p4rt.tmux_send_keys('./ipsec_tunnel_config.sh', delay=15, output=True)
        print(f'{result}')


        print("\n----------------Configure IPsec environment on the host----------------")
        result = host_ipsec.tmux_send_keys(f'cd {host_path}', delay=2, output=True)
        result = host_ipsec.tmux_send_keys('./host_ipsec_config.sh', delay=15, output=True)
        print(result)
        result = host_ipsec.tmux_send_keys('source proxy.sh', delay=10, output=True)
        result = host_ipsec.tmux_send_keys(f'yes|cp -f ipsec.secrets {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/', delay=2, output=True)

        if ipsec_host == '1':
            result = host_ipsec.tmux_send_keys(f'yes|cp -f ipsec.conf_tunnel_1 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf', delay=2, output=True)

        elif ipsec_host == '2':
            result = host_ipsec.tmux_send_keys(f'yes|cp -f ipsec.conf_tunnel_2 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf', delay=2, output=True)

        result = host_ipsec.tmux_send_keys(f'cd {strongSwan_build}', delay=2, output=True)
        result = host_ipsec.tmux_send_keys('source env_setup_acc.sh', delay=15, output=True)

        result = host_ipsec.tmux_send_keys(f'cd {strongSwan_build}//ipsec_offload_plugin/output_strongswan/usr/sbin', delay=2, output=True)


    elif args.command == 'ipsec_performance':
        # Setup a TMUX session, for host interface tuning to test performance
        print("\n----------------Setup TMUX Session and Login to the Host----------------")
        tune_perf = tmux_term(test_setup=test_setup, tmux_name="tune_perf",tmux_override=True)
        cwd = os.getcwd()
        print("cwd  {}".format(cwd))
        result = tune_perf.tmux_send_keys('sudo -s', delay=2, output=True)
        result = tune_perf.tmux_send_keys(f'{host_password}', delay=2, output=True)
        result = tune_perf.tmux_send_keys(f'cd {cwd}/{host_path}', delay=2, output=True)

        print("\n----------------Configure host comm channel for Host - ACC Communication----------------")
        result = tune_perf.tmux_send_keys('ls -lrt', delay=2, output=True)
        print(f'{result}')
        result = tune_perf.tmux_send_keys('./perf_tune.sh', delay=10, output=True)
        print(result)


    elif args.command == 'teardown':

        if len(host_password) == 0:
            print("Enter correct IPU Host root password in config.yaml and retry")
            sys.exit()

        print("\n----------------Teardown Linux Networking with IPsec Offload----------------")

        print("\n----------------Setup TMUX Session, Login to ACC----------------")
        p4rt = tmux_term(test_setup=test_setup, tmux_name="test_p4rt",tmux_override=True)
        result = p4rt.tmux_send_keys(imc_login, delay=2)
        result = p4rt.tmux_send_keys(acc_login, delay=2)
        result = p4rt.tmux_send_keys(f'cd {acc_path}/{host_path}', delay=2, output=True)

        print("\n----------------Cleanup OVS Bridge Configuration----------------")
        command = f'''export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=$P4CP_INSTALL
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
export RUN_OVS=/opt/p4/p4-cp-nws

ovs-vsctl show
ovs-vsctl del-br br-int-0
ovs-vsctl del-br br-tun-0

ip link del TEP0
ovs-vsctl del-br br0
ovs-vsctl show
'''
        result = p4rt.tmux_send_keys(command, delay=20, output=True)
        print(result)

        print("\n----------------Use p4rt-ctl to Delete the rules----------------")
        result = p4rt.tmux_send_keys('./acc_p4rt_delete.sh', delay=60, output=True)
        print(result)
        print("\n----------------Use p4rt-ctl to Dump the rules after cleanup----------------")
        result = p4rt.tmux_send_keys('./4_acc_p4rt_dump.sh', delay=30, output=True)
        print(result)

        print("\n----------------Stop Infrap4d on the ACC----------------")
        infrap4d = tmux_term(test_setup=test_setup, tmux_name="test_infrap4d",tmux_override=True)
        result = infrap4d.tmux_send_keys(imc_login, delay=2, output=True)
        result = infrap4d.tmux_send_keys(acc_login, delay=2, output=True)
        result = infrap4d.tmux_send_keys('ps -aux | grep infrap4d', delay=2, output=True)
        print(result)

    elif args.command == 'create_script':
        print("\n----------------Create IPsec Offload scripts----------------")
        build_p4rt_config(test_setup = test_setup)

    elif args.command == 'copy_script':
        print("\n----------------Create IPsec Offload scripts----------------")
        build_p4rt_config(test_setup = test_setup)
        print("\n----------------Copy IPsec Offload scripts to the ACC----------------")
        test_setup.copy_scripts()

    else:
        parser.print_help()

