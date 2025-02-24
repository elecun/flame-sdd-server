#!/bin/bash

if [ -z "$1" ]
  then
    echo "No Arguments (Target Remote Device IPv4 Address)"
    echo "Usage : ./copy_to_onsite.sh <IP x.x.x.x>"
    exit 1
fi

#copy execution file to the remote
echo "copying files.."
scp ./dk_h_inspector_onsite/*.comp dksteel@"$1":/home/dksteel/flame-sdd-server/bin/x86_64/dk_h_inspector_onsite
#sshpass -p 'ehdrnrwprkd' scp -p -r ./dk_h_inspector_onsite/ dksteel@"$1":/home/dksteel/flame-sdd-server/bin/x86_64/dk_h_inspector_onsite
echo "copied"