#! /bin/bash
IP1=$1
IP2=${2:-$IP1}
SLEEP1=${3:-420}
SLEEP2=${4:-$SLEEP1}
SLEEP3=${5:-$SLEEP1}
echo "Droping packets from $IP1. Sleeping $SLEEP1 seconds."
iptables -I INPUT -s $IP1 -j DROP
sleep $SLEEP1
iptables -D INPUT -s $IP1 -j DROP
echo "Accepting packets from $IP1. Sleeping $SLEEP2 seconds."
sleep $SLEEP2
echo "Droping packets to $IP2. Sleeping $SLEEP3 seconds."
iptables -I OUTPUT -d $IP2 -j DROP
sleep $SLEEP3
iptables -D OUTPUT -d $IP2 -j DROP
echo "Accepting packets from $IP2"
