#!/bin/bash
host=$1 start=$2 username=$3 key=$4 goc=$5 debug=$6 timeout=$7 summary=$8 allowedEvents=$9 exec scl enable python27 - << \EOF
echo $home
source ./esmond.env
python esmonduploader/caller.py -d $debug -s $start -u $host -p -w $username -k $key -g $goc -t $timeout -x $summary -a $allowedEvents
EOF

