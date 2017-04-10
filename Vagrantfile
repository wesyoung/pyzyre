#e -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"
VAGRANTFILE_LOCAL = 'Vagrantfile.local'

$script = <<SCRIPT
# yum clean expire-cache
wget -O /etc/yum.repos.d/zeromq-draft.repo http://download.opensuse.org/repositories/home:/wesyoung:/zeromq/RHEL_7/home:wesyoung:zeromq.repo
rpm --import http://download.opensuse.org/repositories/home:/wesyoung:/zeromq/RHEL_7//repodata/repomd.xml.key

yum -y update
yum install -y gcc python-pip python-devel git libffi-devel openssl-devel htop git "@Development Tools" sqlite-devel \
    python-virtualenvwrapper uuid-devel uuid libuuid-devel systemd-devel mlocate zyre-devel

pip install pip --upgrade
SCRIPT

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = 'geerlingguy/centos7'

  config.vm.provision "shell", inline: $script

  config.vm.provider :virtualbox do |vb|
    vb.customize ["modifyvm", :id, "--cpus", "2", "--ioapic", "on", "--memory", "1024" ]
  end

  if File.file?(VAGRANTFILE_LOCAL)
    external = File.read VAGRANTFILE_LOCAL
    eval external
  end
end
