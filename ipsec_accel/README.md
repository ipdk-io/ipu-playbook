# Linux Networking with IPsec Acceleration

## Introduction

### Default bring-up and image update

- The Intel® Infrastructure Processing Unit is connected to a host server via PCIe.
- A 1GB port from the host server is connected to the IMC 1GB management interface.
- Refer section `3.2.1. Default Bring-Up` in the `Intel IPU Software User Guide` for more information.
- Refer section `3.2.2. Default Update Flow` in the `Intel IPU Software User Guide` and update the images on the IMC and ACC to an SDK release version >= 1.7.0.
- The tool requires the P4 package `fxp-net_linux-networking.pkg` to be loaded on the IPU IMC. Refer the prerequisites section.

### ipsec_accel.py supported features

- The `ipsec_accel.py` tool is executed from the host server connected to an Intel IPU.
- It automates the setup of the Linux networking recipe with IPsec acceleration to the IPU ACC.
- It configures infrap4d on the ACC, programs the p4rt runtime rules to setup the ACC port representors for the host IDPF interfaces and IPU physical ports.
- OVS bridges are created on the ACC with the port representors and configures the IDPF and VF interfaces on the host.
- It sets up the IPsec tunnel or transport mode for offloading crypto functionality to the Inline Crypto Engine.
- It also tunes the interfaces for performance testing.
- Refer section `3.3.1. IPU P4 Quick Start Guide` in the `Intel IPU Software User Guide` for more information.

#### Supported modes

- load_package linux_networking: Copy the P4 artifacts to IMC and ACC, update the P4 package and node policy with IPU reboot.
- setup : Setup OVS bridge configuration with VXLAN encapsulation.
- ipsec_transport : Setup IPsec configuration in transport mode.
- ipsec_tunnel : Setup IPsec configuration in tunnel mode.
- ipsec_performance : Tunes the interfaces for testing performance.
- teardown : Cleanup the  bridge and P4 runtime configuration
- load_package default: Revert to default P4 package and node policy with IPU reboot.

## Supported Topology

### Back-to-back configuration

- 2 IPU adapters are connected to two host servers via PCIe and the IPU Physical Ports on the two servers are connected back to back.
- Host1 IPU Port0 <-----> Host2 IPU Port0
- For IPU Host 1 server copy config_host1.yaml to config.yaml.
- For IPU Host 2 server copy config_host2.yaml to config.yaml.

## Prerequisites

### P4 Package for fxp-net_linux-networking

- The host package `intel-ipu-host-components-<version>.<build number>.tar.gz` contains the example IPU P4 source code, the compiled P4 package and artifacts that is used to set up IPsec acceleration.
- The compiled artifacts for P4 `fxp-net_linux-networking` can be found in the location below after you extract the tar package.
- Update the config.yaml file test_params[p4_artifacts] field with the absolute path to the below folder.

```bash
cd intel-ipu-host-components/P4Tools/P4Programs/artifacts/fxp-net_linux-networking

> ls
total 6.2M
-rw-r--r--. 1 admin12 admin12  46K Sep  3 11:29 p4Info.txt
-rw-r--r--. 1 admin12 admin12 1.4K Sep  3 11:29 entries.json
-rw-r--r--. 1 admin12 admin12 128K Sep  3 11:29 tdi.json
-rw-r--r--. 1 admin12 admin12 639K Sep  3 11:32 context.json
-rw-r--r--. 1 admin12 admin12 949K Sep  3 11:32 fxp-net_linux-networking.s
-rw-r--r--. 1 admin12 admin12 1.5M Sep  3 11:32 fxp-net_linux-networking_<checksum>.pkgo
-rw-r--r--. 1 admin12 admin12 1.5M Sep  3 11:32 fxp-net_linux-networking.pkg
```

### IPU SDK tarball for performance tuning

The IPU SDK tarball `intel-ipu-sdk-source-code-<version>.<build_number>.tar.gz` contains the scripts for performance tuning. Downlopad this tarball from the RDC and extract it. Once extracted the contents will be in Intel_IPU_SDK-<build_number> directory.

### Enabling virtualization

Depends on platform you must make sure the Vt-d, Intel Virtualization Technology, and IOMMU (if the option is present) should be enabled in BIOS setting. If you need SR-IOV for VF interface, enable SR-IOV in BIOS setting. After changing the BIOS setting, you must restart the host.

### Host IDPF driver

- Extract The host package `intel-ipu-host-components-<version>.<build number>.tar.gz`, this contains the IDPF source and pre-built RPMs for RHEL and Rocky Linux.
- If using some other flavor of Linux, run the following commands as a root user to build the IDPF driver from source
- Make sure the same version of IDPF driver is loaded on the host, IMC and ACC

```bash
yum install make
yum install "kernel-devel-uname-r == $(uname -r)"

cd intel-ipu-host-components/IDPF
tar -xvf idpf-<version>.tar.gz
cd idpf-<version>
make
make install
```

- Load the IDPF Driver and create 8 SR-IOV VFs and verify the interfaces come up

```bash
sudo -i
rmmod idpf
modprobe idpf
lsmod | grep idpf
modinfo idpf
echo 8 > /sys/class/net/ens5f0/device/sriov_numvfs
```

- Replace `ens5f0` above with the correct host IDPF interface to create 8 SR-IOV VFs on the host.

## IPU host test environment setup

Before running the script, make sure `/etc/ssh/sshd_config` contains the line for root user.

```bash
PermitRootLogin yes
```

### Install TMUX tool on the localhost

- The tool uses tmux sessions when running the option setup and option teardown.
- Install TMUX on the host.

```bash
Ubuntu/Debian.
sudo apt-get update && sudo apt-get -y install tmux

Redhat/CentOS and other RHEL Distros.
sudo yum install update && sudo yum -y install tmux

Check after installing.
# tmux --help
usage: tmux [-2CDlNuvV] [-c shell-command] [-f file] [-L socket-name]
            [-S socket-path] [-T features] [command [flags]]
```

### Python environment setup for localhost

#### Setup a python virtual environment

```bash
cd ipu-playbook/
python -m venv --copies venv
```

#### Activate the venv and install requirements

```bash
# source venv/bin/activate
(venv)# pip install -r requirements.txt
(venv)# deactivate
```

- requirements.txt

```text
PyYAML
```

- Run the tool **ipsec_accel.py** as a root user.
- Use the python venv to run the tool

```bash
sudo -i
cd ipu-playbook/
source venv/bin/activate
```

## Test Configuration

- The tool uses the config.yaml file to program the rules for IPsec acceleration on the IPU adapter and configure the IDPF interfaces on the host server.

### Back-to-back setup configuration for 2 IPU hosts (config_host1.yaml and config_host2.yaml)

- 2 IPU host servers are connected back-to-back.
- Host1 IPU Port0 <-----> Host2 IPU Port0
- Host1 IPU Port1 <-----> Host2 IPU Port1
- Rename file config_host1.yaml on IPU Host 1 to config.yaml.
- Rename file config_host2.yaml on IPU Host 2 to config.yaml.
- Run ipsec_accel.py on the 2 IPU host servers after copying the respective configs as above.
- Update the file: config.yaml for the specific test setup. Change the management IP, username, and password for IMC and ACC if they are different.
- Update the test_params section as required for the setup with the correct host, IMC and ACC script paths.
- Update the test_params[p4_artifacts] field with the absolute path to fxp-net_linux-networking P4 artifacts folder in intel-ipu-host-components package. This is used to update the P4 package on the IMC.
- Update the test_params [ipu_sdk_path] field with the absolute path of Intel_IPU_SDK-{build_number} which will be obtained by untarring intel-ipu-sdk-source-code-{version}.{build_number}.tar.gz. This is used for performance tuning.
- Update the idpf_interface, vf_interfaces name in the config.yaml of both hosts if the interface names are different.

### IPU Host 1

```bash
> cd ipu-playbook/ipsec_accel
> cp config_host1.yaml config.yaml
```

```bash
> cat config_host1.yaml
host:
  ssh:
    ip: 127.0.0.1
    username: root
    # Update the login password for the IPU Host
    password: ""

imc:
  ssh:
    ip: 100.0.0.100
    username: root
    password: ""

acc:
# SSH to ACC from the IMC
  ssh:
    ip: 192.168.0.2
    username: root
    password: ""

test_params:
    #path fields specify the location where the configuration scripts will be copied to on the Host,IMC and ACC
    host_path: 'ipsec_accel_scripts'
    imc_path: '/mnt/imc/p4_test'
    acc_path:  '/opt/'
    p4_artifacts: '/ipu/MEV-TS/10393/intel-ipu-host-components/P4Tools/P4Programs/artifacts/fxp-net_linux-networking'
    ipu_sdk_path: '/ipu/MEV-TS/11102/Intel_IPU_SDK-11102'
    pf_mac: '00:00:00:00:10:14'
    vf_mac: '00:00:00:00:11:14'
    cxp_num_pages: '5'
    comm_vports: '(([5,0],[4,0]),([0,3],[5,3]),([0,2],[4,3]))'
    # Update the correct IDPF Interface on the Host
    idpf_interface: 'ens2f0'
    # IPs for communication channel between host and ACC
    comm_ip_host: '10.10.0.1'
    comm_ip_acc: '10.10.0.2'
    # Update the list of Host IDPF Interfaces on the Host to Map to ACC Port representors
    # Interfaces ['0','1'] below represents the IPU Physical Port 0 and Port 1 and the remaining as the Host IDPF Vfs
    vf_interfaces: ['0','ens2f0v0','ens2f0v1']
    # These are the ACC Port representors that will be used to map to the interfaces in the above list vf_interfaces. The last PR will be for IPsec application.
    acc_pr_interfaces:  ['enp0s1f0d4','enp0s1f0d5','enp0s1f0d6']
    # The ip_list contains the IP addresses that will be used for the Host IDPF VF interfaces that are mapped to the VM config (using: ip netns). The last IP is for IPsec application
    ip_list: ['192.168.1.101','11.0.0.1']
    # Host VF MAC. For example, Here it will be the MAC of ens2f0v0.
    local_vxlan_tunnel_mac: ['00:1a:00:00:10:14']
    # Remote vxlan IP
    remote_vxlan_ip: ['192.168.1.102']
    # MAC of remote VF v0 interface
    remote_vxlan_mac: ['00:1a:00:00:20:14']
    # User Input for OVS VXLAN Config.
    # Local and remote vtep(virtual tunnel end-point) IPs are used in OVS vxlan config with ACC PRs mapped to host IDPF VF
    local_vtep: ['10.1.1.1']
    remote_vtep: ['10.1.1.2']
    # Tunnel Termination Bridge IP for local and remote peer.
    local_br_tun_ip: ['1.1.1.1']
    remote_br_tun_ip: ['1.1.1.2']
    #Directory where strongswan is built on the host
    strongSwan_build: '/root/ipsec-recipe/'
    #Host 1 or Host 2
    ipsec_host: '1'
```

### IPU Host 2

```bash
> cd ipu-playbook/ipsec_accel/
> cp config_host2.yaml config.yaml
```

```bash
> cat config_host2.yaml
host:
  ssh:
    ip: 127.0.0.1
    username: root
    # Update the login password for the IPU Host
    password: ""

imc:
  ssh:
    ip: 100.0.0.100
    username: root
    password: ""

acc:
# SSH to ACC from the IMC
  ssh:
    ip: 192.168.0.2
    username: root
    password: ""

test_params:
    #path fields specify the location where the configuration scripts will be copied to on the Host,IMC and ACC
    host_path: 'ipsec_accel_scripts'
    imc_path: '/mnt/imc/p4_test'
    acc_path:  '/opt/'
    p4_artifacts: '/ipu/MEV-TS/10393/intel-ipu-host-components/P4Tools/P4Programs/artifacts/fxp-net_linux-networking'
    ipu_sdk_path: '/ipu/MEV-TS/11102/Intel_IPU_SDK-11102'
    pf_mac: '00:00:00:00:20:14'
    vf_mac: '00:00:00:00:21:14'
    cxp_num_pages: '5'
    comm_vports: '(([5,0],[4,0]),([0,3],[5,3]),([0,2],[4,3]))'
    # Update the correct IDPF Interface on the Host
    idpf_interface: 'ens2f0'
    # IPs for communication channel between host and ACC
    comm_ip_host: '10.10.0.1'
    comm_ip_acc: '10.10.0.2'
    # Update the list of Host IDPF Interfaces on the Host to Map to ACC Port representors
    # Interfaces ['0','1'] below represents the IPU Physical Port 0 and Port 1 and the remaining as the Host IDPF Vfs
    vf_interfaces: ['0','ens2f0v0','ens2f0v1']
    # These are the ACC Port representors that will be used to map to the interfaces in the above list vf_interfaces. The last PR will be for IPsec application.
    acc_pr_interfaces:  ['enp0s1f0d4','enp0s1f0d5','enp0s1f0d6']
    # The ip_list contains the IP addresses that will be used for the Host IDPF VF interfaces that are mapped to the VM config (using: ip netns). The last IP is for IPsec application
    ip_list: ['192.168.1.102','11.0.0.2']
    # Host VF MAC. For example, Here it will be the MAC of ens2f0v0.
    local_vxlan_tunnel_mac: ['00:1a:00:00:20:14']
    # Remote vxlan IP
    remote_vxlan_ip: ['192.168.1.101']
    # MAC of remote VF v0 interface
    remote_vxlan_mac: ['00:1a:00:00:10:14']
    # User Input for OVS VXLAN Config.
    # Local and remote vtep(virtual tunnel end-point) IPs are used in OVS vxlan config with ACC PRs mapped to host IDPF VF
    local_vtep: ['10.1.1.2']
    remote_vtep: ['10.1.1.1']
    # Tunnel Termination Bridge IP for local and remote peer.
    local_br_tun_ip: ['1.1.1.2']
    remote_br_tun_ip: ['1.1.1.1']
    #Directory where strongswan is built on the host
    strongSwan_build: '/root/ipsec-recipe/'
    #Host 1 or Host 2
    ipsec_host: '2'
```

## IPsec acceleration tool supported options

### ipsec_accel.py : (P4:fxp-net_linux-networking.p4)

- **ipsec_accel/ipsec_accel.py** makes use of **P4 package: fxp-net_linux-networking.pkg**
- Refer the prerequisite section in this document before proceeding with script execution

```bash
python ipsec_accel.py
usage: ipsec_accel.py [-h] {load_package,setup,ipsec_transport,ipsec_tunnel,ipsec_performance,teardown,create_script,copy_script} ...

Run Linux networking with IPsec Acceleration

positional arguments:
  {load_package,setup,ipsec_transport,ipsec_tunnel,ipsec_performance,teardown,create_script,copy_script}
                        options
    load_package        Update the P4 package on the IMC and reboot IMC
    setup               Setup the complete OVS offload Recipe
    ipsec_transport     Setup the IPsec configs for transport mode
    ipsec_tunnel        Setup the IPsec configs for tunnel mode
    ipsec_performance   Tune for performance
    teardown            Teardown the IPsec offload Recipe
    create_script       Generate configuration scripts in localhost
    copy_script         Copy configuration scripts to IMC and ACC

optional arguments:
  -h, --help            show this help message and exit
```

### 1. load_package

- load_package linux_networking: Update the P4 package on the IMC with fxp-net_linux-networking.pkg, copy the artifacts to IMC and ACC, reboot the IMC for the config changes to take effect.
- load_package default: Revert to the default P4 package and node policy with IMC reboot
- Update the test_params[p4_artifacts] field with the absolute path to fxp-net_linux-networking P4 artifacts folder in intel-ipu-host-components package. This is used to update the P4 package on the IMC.

```bash
python ipsec_accel.py load_package
usage: ipsec_accel.py load_package [-h] {linux_networking,default} ...

positional arguments:
  {linux_networking,default}
    linux_networking    load p4 package fxp-net_linux-networking.pkg and perform IMC reboot
    default             Revert to the default P4 package e2100-default-<version>.pkg and perform IMC reboot

optional arguments:
  -h, --help            show this help message and exit
```

### 2. setup

- Configure IPsec accel on ACC and localhost IDPF VFs.
- Prerequisite: run **python ipsec_accel.py load_package linux_networking** option once to update the p4 package.

```bash
python ipsec_accel.py setup
```

- This will setup OVS offload on the ACC and configure the VFs on localhost.

### 3. ipsec_transport

```bash
python ipsec_accel.py ipsec_transport
```

- This will setup transport mode.
- Prerequisite: run setup.
- Configures TMUX session - test_host_ipsec

### 4. ipsec_tunnel

```bash
python ipsec_accel.py ipsec_tunnel
```

- This will setup tunnel mode.
- Prerequisite: run setup.
- Configures TMUX session - test_host_ipsec

### 5. ipsec_performance

```bash
python ipsec_accel.py ipsec_performance
```

- This will tune for performance testing.
- Prerequisite: run setup, ipsec_transport or ipsec_tunnel.

### 6. teardown

```bash
python ipsec_accel.py teardown
```

- This will tear down the complete OVS setup.

### 7. create_script (optional step used for debug)

- This option will create the configuration shell scripts in the localhost script directory
- The localhost script directory path is specified in **host_path** field in **config.yaml**
- Default localhost script directory path is **ipu-playbook/ipsec_accel/ipsec_accel_scripts**

```bash
python ipsec_accel.py create_script
```

```bash
The helper shell scripts will be created as shown below.
ls -l ipsec_accel/ipsec_accel_scripts
total 100
-rwxr-xr-x. 1 root root  491 Apr  1 12:26 1_host_idpf.sh
-rwxr-xr-x. 1 root root 1167 Apr  1 12:26 2_acc_infrap4d.sh
-rwxr-xr-x. 1 root root 5364 Apr  1 12:26 3_acc_p4rt.sh
-rwxr-xr-x. 1 root root  591 Apr  1 12:26 4_acc_p4rt_dump.sh
-rwxr-xr-x. 1 root root 1288 Apr  1 12:26 5_acc_setup_ovs.sh
-rwxr-xr-x. 1 root root 1100 Apr  1 12:26 6_acc_ovs_bridge.sh
-rwxr-xr-x. 1 root root  210 Apr  1 12:26 7_host_vm.sh
-rwxr-xr-x. 1 root root 1423 Apr  1 12:26 acc_ovs_vxlan.sh
-rwxr-xr-x. 1 root root 3711 Apr  1 12:26 acc_p4rt_delete.sh
-rwxr-xr-x. 1 root root  270 Apr  1 12:26 copy_certs.sh
-rwxr-xr-x. 1 root root 1806 Apr  1 12:26 es2k_skip_p4.conf
-rwxr-xr-x. 1 root root  153 Apr  1 12:26 generate_certs.sh
-rwxr-xr-x. 1 root root  909 Apr  1 12:26 host_ipsec_config.sh
-rwxr-xr-x. 1 root root  484 Apr  1 12:26 ipsec.conf_transport_1
-rwxr-xr-x. 1 root root  482 Apr  1 12:26 ipsec.conf_transport_2
-rwxr-xr-x. 1 root root  647 Apr  1 12:26 ipsec.conf_tunnel_1
-rwxr-xr-x. 1 root root  645 Apr  1 12:26 ipsec.conf_tunnel_2
-rwxr-xr-x. 1 root root   67 Apr  1 12:26 ipsec.secrets
-rwxr-xr-x. 1 root root 1728 Apr  1 12:26 ipsec_tunnel_config.sh
-rwxr-xr-x. 1 root root  515 Apr  1 12:26 perf_tune.sh
-rwxr-xr-x. 1 root root  254 Apr  1 12:26 proxy.sh
-rwxr-xr-x. 1 root root  218 Apr  1 12:26 setup_acc_comm_channel.sh
-rwxr-xr-x. 1 root root  189 Apr  1 12:26 setup_host_comm_channel.sh
-rwxr-xr-x. 1 root root  460 Apr  1 12:26 sync_host_acc_date.sh
```

### 8. copy_script (optional step used for debug)

- This option will create the configuration shell scripts in the localhost script directory (the path can be changed in **host_path:** in **config.yaml**) default path is *ipsec_accel/ipsec_accel_scripts**
- It copies the scripts from localhost to IPU IMC (the path can be changed in **imc_path:** in **config.yaml**) default path is `/mnt/imc/p4_test`)
- It copies the scripts from the IMC to the ACC (the path can be changed in **acc_path:** in **config.yaml**) default path is `/opt/`

```bash
python ipsec_accel.py copy_script
```

## IPsec acceleration setup with automation tool ipsec_accel.py

### STEP 1: Update the P4 package to fxp-net_linux-networking.pkg

- Run the command below once in the IPU localhost server to update the P4 package and setup the node policy changes.
- This will reboot the IMC and ACC for the changes to take effect.

```bash
python ipsec_accel.py load_package linux_networking
```

### STEP 2: OVS Setup

- Run the commands below in the IPU localhost server to configure OVS on the IPU ACC and configure the Host IDPF interfaces.

```bash
python ipsec_accel.py setup
```

### STEP 3. Update config.yaml

Update the local_vxlan_tunnel_mac and remote_vxlan_mac name in the config.yaml of both hosts.

### STEP 4: IPsec Transport

- Run the command below in the IPU localhost server to configure IPsec in transport mode.

```bash
python ipsec_accel.py ipsec_transport
```

- Attach to the TMUX session

```bash
tmux a -t test_host_ipsec
```

- Execute './ipsec start' on both hosts tmux session to establish IPsec Transport mode.
- Check for IPsec session establishment

```bash
host# ./ipsec status

[root@Aurora sbin]# ./ipsec status
Security Associations (1 up, 0 connecting):
    sts-base[1]: ESTABLISHED 3 minutes ago, 192.168.1.101[192.168.1.101]...192.168.1.102[192.168.1.102]
    sts-base{1}:  INSTALLED, TRANSPORT, reqid 1, ESP SPIs: 4f000001_i 93000001_o
    sts-base{1}:   192.168.1.101/32[tcp] === 192.168.1.102/32[tcp]
```

- Send traffic and Check for SADB counters in IMC : 'cli_client -qsS' and encrypted/decrypted counters increment.

```bash
Host 1

host1# ssh admin12@192.168.1.102

[root@Aurora sbin]# ssh admin12@192.168.1.102
admin12@192.168.1.102's password:
Activate the web console with: systemctl enable --now cockpit.socket

Last login: Tue Oct 29 05:54:02 2024 from 192.168.1.101
[admin12@Hestia ~]$


IMC

imc : cli_client -qsS


[root@ipu-imc ~]# cli_client -qsS
No IP address specified, defaulting to localhost
ipsec rx dec packets: 16 bytes: 3221
ipsec rx replay errors: 0
ipsec rx auth failures: 0
ipsec rx misc errors: 0
ipsec rx bad pkts: 0
ipsec tx enc packets: 18 bytes: 2825
ipsec tx misc errors: 0
ipsec tx bad pkts: 0
cisp rx dec packets: 0 bytes: 0
cisp rx auth failures: 0
cisp rx misc errors: 0
cisp rx bad pkts: 0
cisp tx enc packets: 0 bytes: 0
cisp tx misc errors: 0
cisp tx bad pkts: 0
```

- Later after testing traffic and performance execute './ipsec stop' to stop the IPsec session.
- To come out of the tmux session execute ctrl+b d  

### STEP 5: IPsec Performance

- Run the commands below in the IPU localhost server to tune for performance.

```bash
python ipsec_accel.py ipsec_performance
```

- Test with version iperf3.17 or later.
- Make sure IPsec session is established. (./ipsec start in tmux session)
- Example command where one host acts as a server and other as a client

```bash
Server Host 2
iperf3 -s -B 192.168.1.102 -i 1 -p 6000
```

```bash
Client Host 1
iperf3 -t 30 -c 192.168.1.102 -B 192.168.1.101  -i 1  -P 8 -p 6000
```

### STEP 6: IPsec Tunnel

- Run the commands below in the IPU localhost server to configure IPsec in tunnel mode.

```bash
python ipsec_accel.py ipsec_tunnel
```

- Attach to the TMUX session

```bash
tmux a -t test_host_ipsec
```

- Execute './ipsec start' on both ends to establish IPsec Transport mode.
- Check for IPsec establishment

```bash
host# ./ipsec status

[root@Aurora sbin]# ./ipsec status
Security Associations (1 up, 0 connecting):
    sts-base[1]: ESTABLISHED 37 seconds ago, 192.168.1.101[192.168.1.101]...192.168.1.102[192.168.1.102]
    sts-base{1}:  INSTALLED, TUNNEL, reqid 1, ESP SPIs: 6d000001_i 5a000001_o
    sts-base{1}:   11.0.0.1/32[tcp] === 11.0.0.2/32[tcp]
(venv) [root@Aurora sbin]#
```

-Send traffic and check for SADB counters in IMC : 'cli_client -qsS' and encrypted/decrypted counters increment.

```bash
Host

(venv) [root@Aurora sbin]# ssh admin12@11.0.0.2
admin12@11.0.0.2's password:
Activate the web console with: systemctl enable --now cockpit.socket

Last login: Tue Oct 29 06:22:23 2024 from 11.0.0.1
[admin12@Hestia ~]$

IMC

[root@ipu-imc ~]# cli_client -qsS
No IP address specified, defaulting to localhost
ipsec rx dec packets: 80 bytes: 12759
ipsec rx replay errors: 0
ipsec rx auth failures: 0
ipsec rx misc errors: 0
ipsec rx bad pkts: 0
ipsec tx enc packets: 125 bytes: 12867
ipsec tx misc errors: 2
ipsec tx bad pkts: 0
cisp rx dec packets: 0 bytes: 0
cisp rx auth failures: 0
cisp rx misc errors: 0
cisp rx bad pkts: 0
cisp tx enc packets: 0 bytes: 0
cisp tx misc errors: 0
cisp tx bad pkts: 0

server finished responding =======================
```

- If ipsec_performance is already executed, no need to execute it again as tuning parameters are already set.
- Test with version iperf3.17 or later.
- Example command where one host acts as a server and other as a client.

```bash
Server Host 2
iperf3 -s -B 11.0.0.2 -i 1 -p 6000
```

```bash
Client Host 1
iperf3 -t 30 -c 11.0.0.2 -B 11.0.0.1  -i 1  -P 8 -p 6000
```

- Execute './ipsec stop' to stop the IPsec session.
- To come out of the tmux session execute ctrl+b d  

### STEP 7: Revert to Default Configuration

#### IPsec acceleration teardown with automation tool ipsec_accel.py

- Run the tool with option **teardown**

```bash
python ipsec_accel.py teardown
```

#### Revert to Default P4 package

- Run the command below once in the IPU localhost server to update the P4 package and setup the node policy changes.
- This will reboot the IMC and ACC for the changes to take effect.

```bash
python ipsec_accel.py load_package default
```

## IPsec acceleration setup manual execution flow

### 1. Create and copy the script

Execute create_script and copy_script for scripts to be generated and avaialbe in host and ACC.

```bash
python ipsec_accel.py create_script
python ipsec_accel.py copy_script
```

### 2. IMC setup to manually load the P4 package

- Load the P4 package `fxp-net_linux-networking.pkg` on the IMC. Refer Section `IPU P4 Quickstart Guide` in the Intel® Infrastructure Processing Unit Software User Guide
- Login to the IPU IMC from the localhost, default IMC IP is `100.0.0.100`

```bash
ssh root@100.0.0.100
```

- Copy the P4 package `fxp-net_linux-networking.pkg` to the IMC /work/scripts/ directory.
- Update the IMC script `/work/scripts/load_custom_pkg.sh` as shown in the example below.
- Reboot the IMC. On IMC bootup, the P4 package and node policy configuration will be updated as specified in `/work/scripts/load_custom_pkg.sh`.

#### Host 1 IPU IMC

```bash
[root@ipu-imc ~]# cat /work/scripts/load_custom_pkg.sh
#!/bin/sh
CP_INIT_CFG=/etc/dpcp/cfg/cp_init.cfg
echo "Checking for custom package..."
sed -i 's/pf_mac_address = "00:00:00:00:03:14";/pf_mac_address = "00:00:00:00:10:14";/g' $CP_INIT_CFG
sed -i 's/vf_mac_address = "";/vf_mac_address = "00:00:00:00:11:14";/g' $CP_INIT_CFG
if [ -e /work/scripts/fxp-net_linux-networking.pkg ]; then
    echo "Custom package fxp-net_linux-networking.pkg found. Overriding default package"
    cp  /work/scripts/fxp-net_linux-networking.pkg /etc/dpcp/package/
    rm -rf /etc/dpcp/package/default_pkg.pkg
    ln -s /etc/dpcp/package/fxp-net_linux-networking.pkg /etc/dpcp/package/default_pkg.pkg
    sed -i 's/sem_num_pages = .*;/sem_num_pages = 28;/g' $CP_INIT_CFG
    sed -i 's/lem_num_pages = .*;/lem_num_pages = 32;/g' $CP_INIT_CFG
    sed -i 's/mod_num_pages = .*;/mod_num_pages = 2;/g' $CP_INIT_CFG
    sed -i 's/acc_apf = 4;/acc_apf = 16;/g' $CP_INIT_CFG
    sed -i 's/cxp_num_pages = .*;/cxp_num_pages = 5;/g' $CP_INIT_CFG
    sed -i 's/comm_vports = .*/comm_vports = (([5,0],[4,0]),([0,3],[5,3]),([0,2],[4,3]));/g' $CP_INIT_CFG

else
    echo "No custom package found. Continuing with default package"
fi
```

#### Host 2 IPU IMC

- For two IPU host servers connected back-to-back we modify the default MAC addresses of the IPU interfaces.
- The MAC suffix is updated for the pf_mac_address and vf_mac_address in the default node policy `/etc/dpcp/cfg/cp_init.cfg` in the Host 2 IPU IMC.
- This ensures that there are no MAC address conflicts and the Host 2 IPU adapter interfaces use a different MAC address.

```bash
[root@ipu-imc ~]# cat /work/scripts/load_custom_pkg.sh
#!/bin/sh
CP_INIT_CFG=/etc/dpcp/cfg/cp_init.cfg
echo "Checking for custom package..."
sed -i 's/pf_mac_address = "00:00:00:00:03:14";/pf_mac_address = "00:00:00:00:20:14";/g' $CP_INIT_CFG
sed -i 's/vf_mac_address = "";/vf_mac_address = "00:00:00:00:21:14";/g' $CP_INIT_CFG
if [ -e /work/scripts/fxp-net_linux-networking.pkg ]; then
    echo "Custom package fxp-net_linux-networking.pkg found. Overriding default package"
    cp  /work/scripts/fxp-net_linux-networking.pkg /etc/dpcp/package/
    rm -rf /etc/dpcp/package/default_pkg.pkg
    ln -s /etc/dpcp/package/fxp-net_linux-networking.pkg /etc/dpcp/package/default_pkg.pkg
    sed -i 's/sem_num_pages = .*;/sem_num_pages = 28;/g' $CP_INIT_CFG
    sed -i 's/lem_num_pages = .*;/lem_num_pages = 32;/g' $CP_INIT_CFG
    sed -i 's/mod_num_pages = .*;/mod_num_pages = 2;/g' $CP_INIT_CFG
    sed -i 's/acc_apf = 4;/acc_apf = 16;/g' $CP_INIT_CFG
    sed -i 's/cxp_num_pages = .*;/cxp_num_pages = 5;/g' $CP_INIT_CFG
    sed -i 's/comm_vports = .*/comm_vports = (([5,0],[4,0]),([0,3],[5,3]),([0,2],[4,3]));/g' $CP_INIT_CFG
else
    echo "No custom package found. Continuing with default package"
fi
```

- After IMC reboots, the above script will update the P4 package to `fxp-net_linux-networking.pkg` and the default node policy `/etc/dpcp/cfg/cp_init.cfg`.

```bash
[root@ipu-imc ~]# ls -lrt /etc/dpcp/package/
total 2852
-rw-r--r-- 1 root root 1532240 Jan  1 00:00 fxp-net_linux-networking.pkg
lrwxr-xr-x 1 root root      46 Jan  1 00:00 default_pkg.pkg -> /etc/dpcp/package/fxp-net_linux-networking.pkg
drwxr-xr-x 2 root root    4096 Sep 11  2024 runtime_files
-rw-r--r-- 1 root root 1376720 Sep 11  2024 e2100-default-1.0.30.0.pkg
```

### Install IDPF

- Load the IDPF Driver and create 8 SR-IOV VFs and verify the interfaces come up

```bash
sudo -i
rmmod idpf
modprobe idpf
lsmod | grep idpf
modinfo idpf
echo 8 > /sys/class/net/ens5f0/device/sriov_numvfs
```

- Replace `ens5f0` above with the correct host IDPF interface to create 8 SR-IOV VFs on the host.

### 3. IPU P4 Artifacts on ACC

- The scripts expects the P4 artifacts to be available in the directory  as mentioned in config.yaml under test_params [acc_path] in the ACC. By default it is /opt/. Make sure the artifacts corresponds to the release that runs on the IPU.

```bash
[root@ipu-acc ~]# ls /opt/fxp-net_linux-networking
```

### 4. Setup Host to ACC Communication Channel

```bash
On Host
host# cd ipsec_accel/ipsec_accel_scripts
host# ./setup_host_comm_channel.sh
```

```bash
On ACC

acc# cd /opt/ipsec_accel_scripts
acc# ./setup_acc_comm_channel.sh
```

### 5. Sync date between Host and ACC

```bash
On Host

host# ipsec_accel/ipsec_accel_scripts
host# ./sync_host_acc_date.sh
```

### 6. Generate certificates in ACC

```bash
On ACC

acc# cd /opt/ipsec_accel_scripts
acc# ./generate_certs.sh
```

### .7 Copy certificates to Host

```bash
On Host

host# ipsec_accel/ipsec_accel_scripts
host# ./copy_certs.sh
```

### 8. Infrap4d Configuration file

Copy the infrap4d config in **/opt/ipsec_accel_scripts/es2k_skip_p4.conf** to artifact folder **/opt/fxp-net_linux-networking** in the ACC

```bash
On ACC
acc# cp /opt/ipsec_accel_scripts/es2k_skip_p4.conf /opt/fxp-net_linux-networking/
```

### 9. Start Infrap4d

- Use the ipsec_accel_scripts in the ACC to set up infrap4d, p4rt and OVS bridge:

```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./2_acc_infrap4d.sh
```

Wait 30 seconds for infrap4d to initialize and start listening on the server.

### 10. Configure P4 pipeline and add the ACC PR rules

```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./3_acc_p4rt.sh
```

```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./4_acc_p4rt_dump.sh
```

### 11. Set up ACC environment for OVS

```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./5_acc_setup_ovs.sh
```

### 12. Set up OVS Bridge Configuration

```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./acc_ovs_vxlan.sh
```

### 13. Set up VF interfaces configuration on the IPU Host

```bash
host]# cd ipsec_accel/ipsec_accel_scripts
host]# ./7_host_vm.sh
```

Run a Ping Test to Host 2

```bash
host# ip -br a
lo               UNKNOWN        127.0.0.1/8 ::1/128
eno8303          UP             10.232.27.15/23 fe80::c6cb:e1ff:fea7:3c9c/64
eno8403          UP             100.0.0.1/24
ens7f0           DOWN
ens7f1           DOWN
docker0          DOWN           172.17.0.1/16
ens5f0           UP
ens5f0d1         UP
ens5f0d2         UP             10.10.0.1/24
ens5f0d3         UP
ens5f0v0         UP             192.168.1.101/24
ens5f0v1         UP             11.0.0.1/24
ens5f0v2         UP
ens5f0v7         UP
ens5f0v6         UP
ens5f0v5         UP
ens5f0v3         UP
ens5f0v4         UP

host# ping 192.168.1.102
PING 192.168.1.102 (192.168.1.102) 56(84) bytes of data.
64 bytes from 192.168.1.102: icmp_seq=1 ttl=64 time=1107 ms
64 bytes from 192.168.1.102: icmp_seq=2 ttl=64 time=107 ms
64 bytes from 192.168.1.102: icmp_seq=3 ttl=64 time=0.344 ms
64 bytes from 192.168.1.102: icmp_seq=4 ttl=64 time=0.317 ms
^C
--- 192.168.1.102 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3048ms
rtt min/avg/max/mdev = 0.317/303.674/1107.126/465.909 ms, pipe 2
```

### 14. Set up IPsec transport mode

```bash
host# cd ipsec_accel/ipsec_accel_scripts
host# ./host_ipsec_config.sh
host# source proxy.sh
host# yes|cp -f ipsec.secrets {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/


Host 1
host1# yes|cp -f ipsec.conf_transport_1 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf


Host 2
host2# yes|cp -f ipsec.conf_transport_2 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf
```

In the same terminal as above execute ipsec application on both hosts.

```bash
host# cd {strongSwan_build}
host# source env_setup_acc.sh

host# cd {strongSwan_build}/ipsec_offload_plugin/output_strongswan/usr/sbin
host# ./ipsec start
```

In the same terminal Check for IPsec status

```bash
host# cd {strongSwan_build}/ipsec_offload_plugin/output_strongswan/usr/sbin
host# ./ipsec status

[root@Aurora sbin]# ./ipsec status
Security Associations (1 up, 0 connecting):
    sts-base[1]: ESTABLISHED 3 minutes ago, 192.168.1.101[192.168.1.101]...192.168.1.102[192.168.1.102]
    sts-base{1}:  INSTALLED, TRANSPORT, reqid 1, ESP SPIs: 4f000001_i 93000001_o
    sts-base{1}:   192.168.1.101/32[tcp] === 192.168.1.102/32[tcp]
```

Send traffic and check for SADB counters in IMC

```bash
Host 1

host1# ssh admin12@192.168.1.102

[root@Aurora sbin]# ssh admin12@192.168.1.102
admin12@192.168.1.102's password:
Activate the web console with: systemctl enable --now cockpit.socket

Last login: Tue Oct 29 05:54:02 2024 from 192.168.1.101
[admin12@Hestia ~]$


IMC

imc : cli_client -qsS


[root@ipu-imc ~]# cli_client -qsS
No IP address specified, defaulting to localhost
ipsec rx dec packets: 16 bytes: 3221
ipsec rx replay errors: 0
ipsec rx auth failures: 0
ipsec rx misc errors: 0
ipsec rx bad pkts: 0
ipsec tx enc packets: 18 bytes: 2825
ipsec tx misc errors: 0
ipsec tx bad pkts: 0
cisp rx dec packets: 0 bytes: 0
cisp rx auth failures: 0
cisp rx misc errors: 0
cisp rx bad pkts: 0
cisp tx enc packets: 0 bytes: 0
cisp tx misc errors: 0
cisp tx bad pkts: 0
```

### 12. Performance tuning

```bash
On Host

host# cd ipsec_accel/ipsec_accel_scripts
host# ./perf_tune.sh
```

- Test with version iperf3.17 or later.
- Make sure IPsec session is established.
- Example command where one host acts as a server and other as a client
- Server Host 2: iperf3 -s -B 192.168.1.102 -i 1 -p 6000
- Client Host 1: iperf3 -t 30 -c 192.168.1.102 -B 192.168.1.101  -i 1  -P 8 -p 6000

### 13. Set up IPsec tunnel mode

```bash
On ACC

acc# cd /opt/ipsec_accel_scripts
acc# ./ipsec_tunnel_config.sh
```

```bash
On Host

host# cd ipsec_accel/ipsec_accel_scripts
host# ./host_ipsec_config.sh
host# source proxy.sh
host# yes|cp -f ipsec.secrets {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/


Host 1
host1# yes|cp -f ipsec.conf_tunnel_1 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf


Host 2
host2# yes|cp -f ipsec.conf_tunnel_2 {strongSwan_build}/ipsec_offload_plugin/output_strongswan/etc/ipsec.conf
```

In the same terminal as above execute ipsec application on both hosts.

```bash
host# cd {strongSwan_build}
host# source env_setup_acc.sh

host# cd {strongSwan_build}/ipsec_offload_plugin/output_strongswan/usr/sbin
host# ./ipsec start
```

In the same terminal check for IPsec status

```bash
host# cd {strongSwan_build}/ipsec_offload_plugin/output_strongswan/usr/sbin
host# ./ipsec status

[root@Aurora sbin]# ./ipsec status
Security Associations (1 up, 0 connecting):
    sts-base[1]: ESTABLISHED 37 seconds ago, 192.168.1.101[192.168.1.101]...192.168.1.102[192.168.1.102]
    sts-base{1}:  INSTALLED, TUNNEL, reqid 1, ESP SPIs: 6d000001_i 5a000001_o
    sts-base{1}:   11.0.0.1/32[tcp] === 11.0.0.2/32[tcp]
(venv) [root@Aurora sbin]#
```

Send traffic and check for SADB counters in IMC

```bash
Host

(venv) [root@Aurora sbin]# ssh admin12@11.0.0.2
admin12@11.0.0.2's password:
Activate the web console with: systemctl enable --now cockpit.socket

Last login: Tue Oct 29 06:22:23 2024 from 11.0.0.1
[admin12@Hestia ~]$


IMC

[root@ipu-imc ~]# cli_client -qsS
No IP address specified, defaulting to localhost
ipsec rx dec packets: 80 bytes: 12759
ipsec rx replay errors: 0
ipsec rx auth failures: 0
ipsec rx misc errors: 0
ipsec rx bad pkts: 0
ipsec tx enc packets: 125 bytes: 12867
ipsec tx misc errors: 2
ipsec tx bad pkts: 0
cisp rx dec packets: 0 bytes: 0
cisp rx auth failures: 0
cisp rx misc errors: 0
cisp rx bad pkts: 0
cisp tx enc packets: 0 bytes: 0
cisp tx misc errors: 0
cisp tx bad pkts: 0

server finished responding =======================
```

Test performance

- If perf_tune.sh is already executed, no need to execute it again as tuning parameters are already set.
- Test with version iperf3.17 or later.
- Example command where one host acts as a server and other as a client
- Server Host 2: iperf3 -s -B 11.0.0.2 -i 1 -p 6000
- Client Host 1: iperf3 -t 30 -c 11.0.0.2 -B 11.0.0.1  -i 1  -P 8 -p 6000

Stop IPsec application

```bash
host# ./ipsec stop
```

### Optional:  Clean up the configs

Run the tool with option **teardown**

```bash
> python ipsec_accel.py teardown
```

ACC Terminal  : Delete the OVS Bridge Config on the ACC

```bash
#!/bin/sh
export SDE_INSTALL=/opt/p4/p4sde
export P4CP_INSTALL=/opt/p4/p4-cp-nws
export DEPEND_INSTALL=$P4CP_INSTALL
export PATH=/root/.local/bin:/root/bin:/usr/share/Modules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/p4/p4-cp-nws/bin:/opt/p4/p4-cp-nws/sbin
export RUN_OVS=/opt/p4/p4-cp-nws

ovs-vsctl show
ovs-vsctl del-br br-int-0
ovs-vsctl del-br br-tun-0

ip link del TEP0
ovs-vsctl del-br br0
```

ACC Terminal : Delete the p4rt-ctl runtime rules

```bash
acc# cd /opt/ipsec_accel_scripts

acc# ./acc_p4rt_delete.sh

acc# ./4_acc_p4rt_dump.sh
```
