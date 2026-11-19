# Robot manual and rules of the job

All lengths are metres, all angles radians, all times seconds.
Positions are x, y, z in the cell frame: z is up, the table surface is z = 0, and the arm's base axis is the line x = 0, y = 0.

Sections 1 to 4 describe the robot.
Section 5 describes the try, the one stretch of time in which the cell moves on its own.
Sections 6 and 7 describe the job.

## 1. The arm

A seven-joint arm on a pedestal, with a two-finger hand.
You command joint angles. The arm reports joint angles. It does not report where the hand is.
The readings and the camera are not exact. Sections 1.3 and 3 give their limits.

### 1.1 Geometry

Each joint turns about an axis of the link before it.
With all joints at 0 the arm points straight up.

| Joint | Axis | Where | Range |
|---|---|---|---|
| 1 | z | The base axis | -2.9 to 2.9 |
| 2 | y | The shoulder, 0.20 above the table | -2.0 to 2.0 |
| 3 | z | Along the upper arm | -2.9 to 2.9 |
| 4 | y | The elbow, 0.30 beyond the shoulder | -2.4 to 2.4 |
| 5 | z | Along the forearm | -2.9 to 2.9 |
| 6 | y | The wrist, 0.30 beyond the elbow | -2.0 to 2.0 |
| 7 | z | Along the hand | -2.9 to 2.9 |

The hand frame has its origin at the centre of the palm, 0.10 beyond the wrist.
Its pose in the cell frame is

`Rz(q1) T(0,0,0.20) Ry(q2) Rz(q3) T(0,0,0.30) Ry(q4) Rz(q5) T(0,0,0.30) Ry(q6) Rz(q7) T(0,0,0.10)`

where `Rz(a)` and `Ry(a)` are right-handed rotations by `a` about z and y, and `T` is a translation.
The hand's z axis points from the wrist through the palm and along the fingers.
The fingers open and close along the hand's x axis.

### 1.2 Shape

| Part | Shape |
|---|---|
| Pedestal | A fixed cylinder of radius 0.05 from the table to z = 0.12, on the base axis |
| Shoulder | A ball of radius 0.055 centred on the shoulder |
| Upper arm | A rod of radius 0.040 from the shoulder to the elbow, with rounded ends |
| Forearm | A rod of radius 0.033 from the elbow to the wrist, with rounded ends |
| Wrist | A rod of radius 0.028 from the wrist to 0.06 beyond it, with rounded ends |
| Palm | A box centred on the hand frame: 0.060 along hand x, 0.040 along hand y, 0.020 along hand z |
| Fingers | Two bars from 0.010 to 0.070 along hand z. Each is 0.008 thick along hand x and 0.024 wide along hand y, centred on y = 0. Their inner faces are at x = plus and minus half the finger gap |

### 1.3 Motion

| Item | Value |
|---|---|
| Start and park pose | Joints `0 0 0 1.5708 0 1.5708 0`, fingers open at 0.060. By the formula above the palm is then at (0.30, 0, 0.40) with the fingers pointing straight down |
| Path between two joint settings | A straight line in joint space: every joint moves at a constant rate and all arrive together |
| Speed | The joint with furthest to go moves at 0.6 rad/s |
| Following | In a path of several points the arm does not stop at the points in between. It ends on the last point |
| Joint readings | Given to 0.001. Each joint has a fixed zero error of up to 0.003: a joint that reads q is truly at q minus that error. Commands use the same readings, so the arm goes to a commanded angle as it reads it |
| Out-of-range targets | A joint angle outside its range is replaced by the nearest angle inside it |

### 1.4 Fingers

| Item | Value |
|---|---|
| Finger gap | The distance between the inner faces of the fingers, from 0 to 0.060. `finger_gap` is its measured value, given to 0.001 |
| Finger speed | With nothing between them, the fingers cover about half of the remaining distance to the commanded gap every 0.02 |

## 2. Commands

`robot help` lists every command.
The cell moves only while it carries out a command of yours. Between commands nothing changes, however long you take.

These two work at any time and cost nothing:

- `robot state` gives `joints` (seven angles), `finger_gap`, `try` (`not started`, `running` or `over`), `actions_left` and `finished`. While the try is running it also gives `step` (steps taken), `steps_left`, `time` (seconds since the try began) and `blocked` (section 5.3).
- `robot look FILE` saves a PNG of what the camera sees now.

These work outside the try (section 5):

- `robot joints Q1 Q2 Q3 Q4 Q5 Q6 Q7` moves the arm to one joint setting.
- `robot path FILE` moves the arm through 1 to 200 joint settings in order without stopping in between. FILE holds a JSON list of lists of seven angles.
- `robot grip WIDTH` sets the finger gap. The reply gives the gap reached.
- `robot finish` ends the session. Nothing is accepted afterwards.

The reply to `joints` and `path` gives the state, `blocked`, and `points_reached`: how many of the points the arm passed or reached.
Each `robot joints`, `robot path` and `robot grip` is one action.
You may take 10 actions before you start the try, and 30 after the try is over. `actions_left` is what remains of the allowance you are in.
The try starts only from the park pose (section 6.1), so getting back there is one of the 10.
Looking, reading the state, starting the try and taking its steps are free.
There is no undo and no reset.

## 3. The camera

The robot has one camera, in the palm.

| Item | Value |
|---|---|
| Position | 0.011 from the hand frame's origin along hand z, to within 0.003 in any direction |
| Direction | Along hand z, out between the fingers, to within 1.5 degrees. The picture's right and up are turned by the same small error |
| Image | 480 by 480 pixels. In the image, right is the hand's +x and up is the hand's -y |
| Field of view | 60 degrees in both directions |
| Lens | Close to a pinhole with square pixels and the image centre on the viewing axis. A point's image is displaced along the line from the image centre by up to 2 percent of its distance from the centre: nothing at the centre, most at the corners. The displacement is the same in every picture |
| Noise | Every pixel carries noise of about 2 percent of full scale, and the brightness of a whole picture varies by up to 3 percent from one picture to the next |
| Fixed errors | The mount and lens errors do not change during a session |

## 4. When a move is blocked

`"blocked": true` in a reply means the arm did not complete the move.
Either something stopped it on the way, or it ended more than 0.002 from the last point on some joint.
The rest of the path is dropped, and the arm holds the joint angles at which it came to rest.

The arm stops only when something resists it firmly.
It pushes light or loose things along without stopping.
Something held in the fingers that is pressed hard against something firm can stop the move too.

## 5. The try, step by step

The try is the only time the cell moves on its own.
It lasts 4.0 seconds of robot time, in 20 steps of 0.2, whatever happens in it.
Robot time moves only when you take a step. Between steps the cell is frozen, however long you take.

| Command | What it does |
|---|---|
| `robot try` | Starts the try at time 0.00. It is refused unless the arm is parked (section 6.1). The cell does not move yet |
| `robot step [FILE]` | Takes one step: the cell moves on by 0.2 and stops. FILE may hold a JSON list of up to three actions |
| `robot skip` | Takes all the remaining steps of the try, with no new actions |

While the try is running, `robot state` and `robot look` work between steps, and the other commands of section 2 are refused.
`robot look` gives the picture at the time the cell has reached.

### 5.1 Actions

An action is a JSON object with `at` and with one or more of `joints`, `grip` and `stop`, for example `{"at": 0.03, "joints": [q1, q2, q3, q4, q5, q6, q7], "grip": 0.0}`.

- `joints` is a move: the arm goes to these joint angles in a straight line in joint space at its usual speed.
- A move cannot be changed once it is sent. The arm carries out one move at a time. A move whose time comes while another is under way waits, and starts within 0.01 of the end of the moves before it. Moves wait in the order of their times.
- `"stop": true` stops the arm where it is and drops the move under way and the moves waiting behind it. Moves whose time comes after the stop are not dropped, but none starts sooner than 0.2 after the stop. `stop` and `joints` cannot be in the same action.
- `grip` sets the commanded finger gap. The fingers act at once, whatever the arm is doing.
- `at` is one of 0.00, 0.01, up to 0.19. It is the time from the start of the step in which the action is carried out. Left out, it is 0.00.
- Actions are carried out in the order of their `at`, and actions with the same `at` in the order they are listed.

If any action in FILE is not valid, the step is not taken and nothing moves.

### 5.2 The delay

The actions you send with a step are not carried out during that step.
They are carried out during the step after it.

| You send | The cell moves from | Actions carried out in that time | The state and the picture are then at |
|---|---|---|---|
| `robot try` | | none | 0.00 |
| step 1 with actions A1 | 0.00 to 0.20 | none | 0.20 |
| step 2 with actions A2 | 0.20 to 0.40 | A1, each at 0.20 plus its `at` | 0.40 |
| step n with actions An | 0.2 (n - 1) to 0.2 n | A(n-1), each at 0.2 (n - 1) plus its `at` | 0.2 n |
| step 20 with actions A20 | 3.80 to 4.00 | A19. A20 is never carried out | 4.00 |

So what you decide after seeing the cell at time t takes effect between t + 0.20 and t + 0.40.
`robot skip` still carries out the actions sent with the step before it.

### 5.3 While the try runs and when it ends

If something stops the arm during the try (section 4), it counts as a stop at that moment: the arm holds where it came to rest, the move under way and the moves waiting behind it are dropped, and no move starts sooner than 0.2 after.
`blocked` in the state is true after any step in which this happened, and false after a step in which it did not.
After step 20 the try is over. The arm stops where it is, moves that have not finished are dropped, the fingers keep their commanded gap, and the commands of section 2 work again.

## 6. The job

### 6.1 The try

There is one try.
The try starts from the park pose.
`robot try` is refused, and nothing is used up, unless every joint is within 0.02 of the park pose and the finger gap is at least 0.055.
The part is released at time 0.00 of the try, at the top of a track, and travels once down its length.
The part has to be taken from the track while it moves, with a two-finger grip.
Once a part is in the hand, the only thing left to do with it is to let it go into the basket.
The basket is the open box that holds three blocks at the start.

### 6.2 How the try is judged

The robot does not tell you how the try stands.
No reply says whether the part was caught, fouled, lost, dropped or delivered.
The cell keeps track of it by the rules below, and that is what is checked at the end.

| The try stands at | When |
|---|---|
| `foul` | The arm touched the part and both fingers were not holding it within 0.05 of that first touch, or the arm touched the part for more than 0.05 in all without both fingers holding it, or held it with both fingers and then let it go, or the part touched anything other than the track and the arm before it was caught. A try that is fouled stays fouled |
| `lost` | The part passed the end of the track, or left the track, or was not yet caught when the try ended |
| `caught` | Both fingers held the part, it touched nothing else, and it was lifted at least 0.02 clear of the track, for 0.2 without a break |
| `dropped` | After being caught, the part left the hand anywhere but in the basket: no finger touched it for 0.02 while its centre was not between the inner faces of the basket's walls. A part let go over the basket that then comes to rest higher than the limit below, or leaves the basket, is dropped too |
| `delivered` | After being caught, the part was let go into the basket and came to rest there: its centre between the inner faces of the basket's walls and no more than 0.012 above their top, moving slower than 0.02 a second, with no finger touching it, for 0.2 without a break |

Both fingers hold the part when both touch it while they are being driven closed onto it: the commanded finger gap is at least 0.002 smaller than the gap reached.
Fingers that stand still at about the part's width, so that the part stops between them, do not hold it.
A part that was caught can be dropped or delivered during the try or after it.

## 7. When the job is done

After `robot finish`, the cell's true state is checked. All of these must hold:

1. The try stands at `delivered`, and the part is still inside the basket: its centre between the inner faces of the basket's walls and no more than 0.012 above their top.
2. The three blocks that were in the basket at the start are still inside it: each centre between the inner faces of the basket's walls and no more than 0.05 above their top.
3. The arm is parked: every joint is within 0.02 of the park pose, and the finger gap is at least 0.055.
4. `robot finish` has been run, and no more than 10 actions were taken before the try and no more than 30 after it.

There is no partial credit.
