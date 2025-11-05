import subprocess

ssh_command = [
    "sshpass", "-p", "Ehdrnrwprkd1",
    "ssh",
    "-T",
#    "-o", "UserKnownHostsFile=/dev/null",
#    "-o", "StrictHostKeyChecking=no",
    "dksteel@192.168.1.52",
    "cp /volume1/sdd/file_list.txt /volume1/sdd/defect_images/"
]

subprocess.run(ssh_command)