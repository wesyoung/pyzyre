#e -*- mode: ruby -*-
# vi: set ft=ruby :

$script = <<SCRIPT
echo "alias aptitude='aptitude -F \"%c %p %d %V\"'" >> /home/ubuntu/.bashrc

wget -nv http://download.opensuse.org/repositories/network:messaging:zeromq:git-draft/xUbuntu_16.04/Release.key -O Release.key
apt-key add - < Release.key

# https://software.opensuse.org/download/package.iframe?project=network:messaging:zeromq:git-draft&package=zyre
echo 'deb http://download.opensuse.org/repositories/network:/messaging:/zeromq:/git-draft/xUbuntu_16.04/ /' > /etc/apt/sources.list.d/zeromq.list

apt-get update
apt-get install -y aptitude python-pip python-dev git htop virtualenvwrapper python2.7 python-virtualenv cython git \
    build-essential libtool pkg-config autotools-dev autoconf automake cmake libpcre3-dev valgrind libffi-dev zip \
    uuid-dev libzyre-dev

pip install pip --upgrade

SCRIPT

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"
VAGRANTFILE_LOCAL = 'Vagrantfile.local'

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = 'ubuntu/xenial64'
  config.vm.provision "shell", inline: $script

  config.vm.provider :virtualbox do |vb, override|
    vb.customize ["modifyvm", :id, "--cpus", "2", "--ioapic", "on", "--memory", "512" ]
  end

  if File.file?(VAGRANTFILE_LOCAL)
    external = File.read VAGRANTFILE_LOCAL
    eval external
  end
end
