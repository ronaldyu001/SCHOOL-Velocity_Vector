### **LiDAR-Aware Robust Reinforcement Learning for Sim-to-Real Autonomous Racing**

The central question:

> **Does adding LiDAR actually make a DeepRacer policy more robust to disturbances that were not present during training?**

That is much more publishable than simply saying:

> “We trained a DeepRacer using LiDAR.”

There is already substantial work on DeepRacer, sim-to-real, domain randomization, and LiDAR-based autonomous racing. For example, the original AWS DeepRacer research demonstrated sim-to-real transfer and domain randomization, while later work has compared architectures using LiDAR and physical-vehicle evaluation.)

So your novelty should be the **experimental question and evaluation protocol**, not claiming that LiDAR or domain randomization itself is new.

---

# Your strongest 2-week experiment

I would build a **4-condition experiment**.

| Model | Camera | LiDAR | Domain randomization |
| ----- | -----: | ----: | -------------------: |
| A     |      ✓ |     — |                    — |
| B     |      ✓ |     ✓ |                    — |
| C     |      ✓ |     — |                    ✓ |
| **D** |      ✓ |     ✓ |                    ✓ |

Your hypothesis:

> **H1:** LiDAR improves robustness to obstacles and lateral disturbances.
> **H2:** Domain randomization improves robustness to environmental/sensor variation.
> **H3:** Combining LiDAR + domain randomization produces the most robust sim-to-real policy.

This gives you an actual **factorial-style ablation study**, rather than one model.

And it fits the Evo hardware particularly well because AWS describes the LiDAR as providing information about objects behind and beside the vehicle, whereas the front camera primarily observes the forward environment. ([AWS Documentation][3])

---

# What I would measure

Don't make **lap time** your only metric.

You need a robustness story.

### 1. Completion rate

Run, for example:

**20 trials/model**

Measure:

$$
CompletionRate =
\frac{\text{successful laps}}{\text{total trials}}
$$

---

### 2. Collision rate

Especially important for the LiDAR experiment.

$$
CollisionRate =
\frac{\text{collision trials}}{\text{total trials}}
$$

---

### 3. Off-track rate

Measure how frequently the vehicle leaves the valid track region.

---

### 4. Lap time
T_lap

A model that is 0.5 seconds faster but crashes twice as often is telling a very different story.

---

### 5. Intervention/recovery count

This could become a particularly nice metric.

For every disturbance:

**Did the policy recover without human intervention?**

For example:

| Trial | Disturbance | Recovered? | Recovery time |
| ----- | ----------- | ---------: | ------------: |
| 1     | obstacle    |        Yes |         1.4 s |
| 2     | lighting    |        Yes |         0.8 s |
| 3     | obstacle    |         No |             — |

Then calculate:

$$
RecoveryRate =
\frac{\text{successful recoveries}}
{\text{disturbance events}}
$$

---

# The really interesting experiment

Don't just test the model on the **same environment it trained on**.

Create a **held-out disturbance set**.

### Training

Train using:

* normal lighting
* normal track
* normal friction
* normal sensor noise

Then introduce disturbances **only during evaluation**.

For example:

### Test set A — visual shift

* bright lighting
* darker lighting
* different background
* track-color variation

### Test set B — sensor noise

* camera noise
* LiDAR noise
* missing LiDAR readings

### Test set C — physical disturbance

If you have access to the physical Evo:

* obstacle introduced
* slightly different track conditions
* different starting position
* perturbation around the vehicle

This gives you a very clean research statement:

> **Train on normal conditions → test under unseen conditions.**

That is substantially more interesting than simply reporting training reward.

---

# One experiment I especially like for your paper

## LiDAR dropout

This could make your project more interesting.

Train:

**Camera + LiDAR**

Then during evaluation:

### 100% LiDAR

Normal condition.

### 50% LiDAR

Randomly remove half of LiDAR observations.

### 25% LiDAR

### 0% LiDAR

Now you can plot:

**LiDAR availability → completion rate**

That gives you a robustness curve.

For example, conceptually:

```text
Completion
100% |             ●
 90% |          ●
 80% |       ●
 70% |
 60% |   ●
 50% |
     +--------------------
       0  25  50  75 100
          LiDAR availability
```

Don't invent the values—you generate them experimentally.

The interesting research question becomes:

> **How much does a multimodal autonomous policy degrade when one sensing modality becomes unreliable?**

That's a legitimate robustness question and is more compelling than “LiDAR improves performance.”

---

# Even better: sensor disagreement

You have camera + LiDAR.

You can investigate:

> **What happens when the sensors disagree?**

Example:

* camera says track is clear
* LiDAR detects obstacle

or

* camera sees track boundary
* LiDAR becomes noisy

You could define a simple **sensor disagreement condition** and evaluate the policy.

That gives you a nice paper framing:

### **Robust Multimodal Perception Under Sensor Degradation in Sim-to-Real Autonomous Racing**

That's potentially stronger academically than a generic DeepRacer project.

---

# Your 2-week plan

## Days 1–2 — Establish baseline

Don't change everything yet.

Run:

### Baseline 1

Camera only.

Record:

* reward
* lap time
* completion rate
* crashes
* off-track events

Run multiple trials.

**Goal:** establish reproducibility.

---

# Day 3 — Camera + LiDAR

Train/evaluate the Evo configuration.

Compare:

**Camera**

vs.

**Camera + LiDAR**

Don't worry about fancy modifications yet.

Your first research table becomes:

| Model          | Completion | Collision | Off-track | Lap time |
| -------------- | ---------: | --------: | --------: | -------: |
| Camera         |          X |         X |         X |        X |
| Camera + LiDAR |          X |         X |         X |        X |

---

# Days 4–5 — Domain randomization

Introduce controlled randomization.

Don't randomize everything simultaneously.

Choose **3–4 variables**:

* lighting
* camera noise
* LiDAR noise
* starting position
* track appearance

The original DeepRacer work explicitly used randomized conditions such as action noise and starting points to evaluate generalization.

Your contribution is to systematically compare those effects with the multimodal Evo configuration.

---

# Day 6 — Train the four models

Ideally:

```text
                    Domain Randomization
                     No             Yes
                 -------------------------
Camera       |      A              C
Camera+LiDAR |      B              D
```

If training time is constrained, prioritize:

**A → B → D**

and treat C.

---

# Days 7–8 — Stress testing

This is where your project becomes research.

For each model:

### Normal

### Lighting shift

### Sensor noise

### LiDAR dropout

### Different starting position

### Obstacle

Run repeated trials.

Don't cherry-pick successful runs.

---

# Day 9 — Physical Evo evaluation

If you have access to the physical vehicle, this is extremely valuable.

AWS's DeepRacer workflow explicitly supports training/evaluation in simulation followed by deployment to the physical vehicle.

Measure:

* successful laps
* collisions
* lap time
* recovery
* off-track
* sensor failures

Even a relatively small physical evaluation is valuable if it is **systematic and repeated**.

---

# Day 10 — Statistical analysis

Calculate:

### Mean

$$
\bar{x}
$$

### Standard deviation

$$
\sigma
$$

### Relative improvement

$$
Improvement =
\frac{X_{new}-X_{baseline}}
{X_{baseline}}\times100
$$

For failure metrics, obviously interpret the direction appropriately.

You can also report confidence intervals if you have enough repeated trials.

---

# Day 11 — Make the key figures

You only need ~4 excellent figures.

### Figure 1

Architecture

```text
Camera ───────┐
              ├──> RL Policy ──> Steering/Throttle
LiDAR ────────┘
```

### Figure 2

Camera vs Camera+LiDAR

### Figure 3

Effect of domain randomization

### Figure 4

LiDAR dropout robustness curve

That last figure could become your poster's most interesting result.

---

# Day 12 — Write the paper

Structure:

### Abstract

Problem → method → experiment → results → conclusion.

### Introduction

Explain:

**Sim → Real gap**

↓

**Sensor/environment variation**

↓

**Need for robust policy**

### Research Questions

I'd explicitly state:

**RQ1:** Does LiDAR improve autonomous racing robustness?

**RQ2:** Does domain randomization improve generalization?

**RQ3:** Does multimodal sensing + domain randomization improve robustness under unseen disturbances?

**RQ4:** How sensitive is the policy to LiDAR degradation?

That's a legitimate experimental paper structure.

---

# Day 13 — Reproducibility

This is particularly important.

Create:

```text
deepracer-robustness/
│
├── configs/
├── reward_functions/
├── experiments/
├── results/
├── plots/
├── README.md
└── paper/
```

Document:

* sensor configuration
* reward function
* training parameters
* random seeds
* track
* number of episodes
* evaluation trials
* disturbance parameters

This makes it much easier for someone else to reproduce your results.

---

# Day 14 — Poster + paper polish

Your poster should have one giant message:

> **Can multimodal sensing and domain randomization make DeepRacer policies more robust to unseen conditions?**

Then:

### Problem

Sim-to-real robustness.

### Method

Camera + LiDAR + controlled perturbations.

### Experiment

4 model configurations.

### Results

Completion / collision / recovery / lap time.

### Finding

Whatever the actual data shows.

Don't decide the conclusion beforehand.

---

# What would make this publishable?

I'd think about the paper in three levels.

### Level 1 — Workshop/student research paper

**Very achievable in 2 weeks.**

A systematic DeepRacer robustness study with proper ablations and physical evaluation.

---

### Level 2 — Stronger ML/robotics workshop paper

Add:

**sensor degradation + domain randomization + physical validation**

This gives you a more coherent contribution.

---

### Level 3 — More ambitious research

Develop an actual **adaptive sensor-fusion policy**.

For example:

```text
Camera ───────┐
              │
              ├── Sensor Reliability Module
LiDAR ────────┘
                       ↓
                 Adaptive Fusion
                       ↓
                  RL Policy
                       ↓
                 Vehicle Action
```

The model dynamically determines how much to trust LiDAR vs camera.

But **I would NOT attempt this in your two-week window unless your existing pipeline is already working extremely well.**

---

# One important thing for your GHC AWS poster

Your project should not read like:

> “I used AWS DeepRacer to learn reinforcement learning.”

That's educational.

Instead:

> **“I investigated the robustness of multimodal reinforcement-learning policies under unseen sensor and environmental disturbances, using AWS DeepRacer Evo as a controlled sim-to-real testbed.”**

That's research.

And the distinction matters because AWS itself now describes DeepRacer as a platform for experimenting with sensor inputs and sim-to-real transfer methods.

Also, existing literature has already studied LiDAR-based racing and sim-to-real transfer, including physical-vehicle evaluation, so your paper should **not claim “first LiDAR DeepRacer research”** or similar.

## My recommendation for your exact 2 weeks

If your goal is **GHC poster + potential paper**, I'd prioritize:

**Camera vs LiDAR**
→ **+ domain randomization**
→ **unseen disturbances**
→ **LiDAR dropout**
→ **physical Evo validation**
→ **statistical comparison**

That gives you a coherent story rather than adding lots of unrelated ML techniques.

If you can get **4 models × 5 disturbance conditions × 10–20 trials**, you could have a surprisingly solid experimental paper from the hardware you already have.
