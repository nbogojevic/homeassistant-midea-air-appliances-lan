echo "Droping packets from $IP_ADDRESS. Sleeping 15 minutes."
iptables -I INPUT -s $IP_ADDRESS -j DROP
sleep 900
iptables -D INPUT -s $IP_ADDRESS -j DROP
echo "Accepting packets from $IP_ADDRESS. Sleeping 10 minutes."
sleep 600
echo "Droping packets to $IP_ADDRESS. Sleeping 15 minutes."
iptables -I OUTPUT -s $IP_ADDRESS -j DROP
sleep 900
iptables -D OUTPUT -s $IP_ADDRESS -j DROP
echo "Accepting packets from $IP_ADDRESS"
