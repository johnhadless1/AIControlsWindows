# AIControlsWindows
uses the cloud / local AI model then let them connect into Windows computer (VNC) then get (torture) them to use it

### warning: this isnt 100% perfect best method for AI to use windows computer, but it just works.

_(note AI models will control Windows computer like drunk person who dont know how computer works)_
_(technically linux or macos may work but idk if it would work though, windows is only works and tested)_

# Setting up

Host computer = AI will control it
Client computer = Where AI stuff magic happens

you have to first install tightVNC in host computer for screenshot and stuff.

then get python in Windows computer for "winserver.py"

and you would able to run "clientcloudai.py" or "clientlocalai.py" of your choice on client computer

### YOU HAVE TO EDIT CONFIG STUFF IN "clientcloudai.py" or "clientlocalai.py" BLAH!!!!!

# How connect

First, you have to get the host computer's IP (or local IP) for VNC connection.

and as you connected the AI into the host computer, as you first run the client python file (clientcloudai.py or clientlocalai.py)

you would able to prompt something for AI to do in host computer. or better, you would leave it blank and it would prompt "Youre on your own. Do something as you want." automatically.

1. run winserver.py in host computer
2. run client python file (accusing you have config stuff already set up)
3. prompt thing or blank prompt
4. profit *(poorly)*
