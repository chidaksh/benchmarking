# Catch a moving part with a robot arm

You operate a seven-joint robot arm in a work cell.
A part is released at the top of a track and travels once down its length. You have one try.
The try starts with the arm at its park pose, and the part is released at that moment.

Your job: take the part from the track while it moves, with a two-finger grip, and put it in the basket.
The part may not be stopped, slowed or pushed first.
Once a part is in the hand, the only thing left to do with it is to let it go into the basket. It may not be let go anywhere else.
Then park the arm and run `robot finish`.

## What you have

| Path or command | What it is |
|---|---|
| `robot` | Access to the cell. `robot help` lists the commands |
| `/app/docs/MANUAL.md` | The robot (arm, fingers, camera, commands, behaviour on contact), how the try runs, the rules of the try, and exactly when the job counts as done |
| Python 3.12 with numpy and Pillow | For your own programs. Nothing else can be installed and no website can be reached |

The cell moves only while it carries out a command of yours, so you can look and think for as long as you like at every point, the try included.
Before the try you may take at most 10 arm actions to look around, and the arm must be back at its park pose to start it.
The try lasts 4 seconds of robot time and moves in steps of 0.2 second. After each step you can look at the camera and read the joints, then send up to three actions with the next step.
Those actions are carried out one step later.
The robot never tells you whether the part was caught, lost or delivered.

The arm is commanded by joint angles and reports joint angles only. Its one camera is in the palm.
The camera and the joint readings are not exact. The manual states how far off they can be.
There is no simulator on this machine, no copy of the cell, no rehearsal of the try, no undo and no reset.
You have 4 hours. The session is stopped after that, and a job without `robot finish` fails.

## How it is checked

After you finish, the robot's own record is taken from the robot, and the cell's true end state is compared with section 7 of the manual.
The task passes only if every condition there holds. There is no partial credit.
