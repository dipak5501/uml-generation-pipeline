# Preliminary Survey: XR Performance Testing Practices and Benchmark Needs

Filled copy of the XR performance-testing survey. Highlighted choices from the Word file are marked **[X]** below.

### Study Purpose

This survey investigates how XR developers identify and evaluate performance issues, what challenges they experience when reproducing and validating such issues, and what capabilities would make a shared XR performance benchmark useful.

For this survey, XR includes virtual reality (VR), augmented reality (AR), and mixed reality (MR) applications.

## Section A. Background and Screening

#### Q1. Have you participated in the development, testing, maintenance, or performance optimization of an XR application?

- **[X] Yes**
- No
[If No: end survey or direct to a separate non-practitioner path.]

#### Q2. Which types of XR applications have you worked with?

Select all that apply.

- **[X] Virtual Reality (VR)**
- **[X] Augmented Reality (AR)**
- **[X] Mixed Reality (MR)**
- Other: _______
#### Q3. Approximately how much experience do you have developing or testing XR applications?

- Less than 1 year
- **[X] 1–2 years**
- 3–5 years
- 6–10 years
- More than 10 years
#### Q4. Which roles have you performed in XR projects?

Select all that apply.

- **[X] Software developer**
- **[X] XR developer**
- **[X] Tester / QA engineer**
- Performance engineer
- **[X] Researcher**
- Technical lead / architect
- Product or project manager
- **[X] Designer**
- Other: _______
#### Q5. Which XR development platforms or engines have you worked with?

Select all that apply.

- **[X] Unity**
- Unreal Engine
- OpenXR
- ARCore
- ARKit
- WebXR
- Native platform SDKs
- **[X] Other: A-Frame, Mobile AR**
#### Q6. Which XR hardware platforms have you worked with?

Select all that apply.

- **[X] Standalone VR headset**
- PC-tethered VR headset
- **[X] Mobile / handheld AR**
- **[X] Head-mounted AR/MR device**
- Other: _______
#### Q7. How frequently have you personally diagnosed or investigated XR performance problems?

- Never
- Rarely
- Occasionally
- **[X] Frequently**
- Very frequently
#### Q8. Have you personally implemented or reviewed a change intended to improve XR application performance?

- **[X] Yes**
- No
- Unsure
## RQ1. What properties and contextual factors do XR developers use to determine whether observed behavior constitutes a performance issue?

### Section B. Identifying XR Performance Issues

#### Q9. When deciding whether an XR application has a performance problem, how important are each of the following?

Rate each item:

1 = Not important
2 = Slightly important
3 = Moderately important
4 = Very important
5 = Essential
N/A = Not applicable to my work

- **[X] Frame time  →  5 Essential**
- **[X] Frame rate  →  5 Essential**
- **[X] Dropped frames  →  5 Essential**
- **[X] Reprojected or repeated frames  →  4 Very important**
- **[X] Motion-to-photon latency  →  5 Essential**
- **[X] Interaction latency / responsiveness  →  5 Essential**
- **[X] CPU utilization  →  4 Very important**
- **[X] GPU utilization  →  4 Very important**
- **[X] Memory usage  →  4 Very important**
- **[X] Memory allocation or garbage-collection events  →  5 Essential**
- **[X] Energy consumption  →  4 Very important**
- **[X] Battery drain  →  4 Very important**
- **[X] Device temperature  →  4 Very important**
- **[X] Thermal throttling  →  4 Very important**
- **[X] Model-inference latency  →  3 Moderately important**
- **[X] Tracking latency or stability  →  5 Essential**
- **[X] Visual quality degradation  →  4 Very important**
- **[X] Interaction quality or correctness  →  4 Very important**
#### Q10. Are there other properties you use to determine whether an XR application has a performance issue?

Open response:

- **[X] Judder or swaying during head motion, tracking loss or pose jumps, passthrough lag in MR, shader-compilation and asset-streaming hitches, and input-to-photon latency. In Unity I also watch GC spikes and camera/render-scale changes that keep the frame counter green while comfort drops.**
#### Q11. When deciding whether observed performance degradation constitutes an actual issue, how important are the following characteristics?

Use the same 1–5 scale.

- **[X] Magnitude of the degradation  →  5 Essential**
- **[X] Frequency of the degradation  →  4 Very important**
- **[X] Duration of the degradation  →  4 Very important**
- **[X] Number of consecutive performance violations  →  5 Essential**
- **[X] Whether the degradation is reproducible  →  5 Essential**
- **[X] Whether it occurs during a particular user action  →  4 Very important**
- **[X] Whether it occurs in a particular scene or environment  →  4 Very important**
- **[X] Whether it occurs only on particular hardware  →  4 Very important**
- **[X] Whether it occurs after sustained use  →  4 Very important**
- **[X] Whether users can perceive the degradation  →  5 Essential**
- **[X] Whether it affects comfort  →  5 Essential**
- **[X] Whether it interferes with task completion  →  5 Essential**
- **[X] Whether it causes increased energy consumption or heating  →  4 Very important**
#### Q12. Which THREE factors are most important when you decide whether an observed degradation should be treated as a performance issue?

Select up to three.

- Magnitude
- Frequency
- Duration
- Consecutive violations
- Reproducibility
- User activity
- Scene / environment
- Hardware or device
- Thermal state / sustained execution
- **[X] Perceptibility**
- **[X] User comfort**
- **[X] Task impact**
- Energy or battery impact
- Other: _______
#### Q13. Consider an XR application that normally meets its frame-time target. Which of the following would you consider a performance issue?

For each, select:

- Definitely not an issue
- Probably not an issue
- Unsure / depends
- Probably an issue
- Definitely an issue
Scenarios:

- **[X] One isolated frame-time spike during a 20-minute session.  →  Probably not an issue**
- **[X] Several isolated frame-time spikes distributed throughout a session.  →  Unsure / depends**
- **[X] A short burst of consecutive missed frames.  →  Probably an issue**
- **[X] Repeated bursts whenever the user performs a specific interaction.  →  Definitely an issue**
- **[X] Performance degradation whenever the user enters a particular scene.  →  Definitely an issue**
- **[X] Performance degradation that appears only after extended use as the device becomes warm.  →  Definitely an issue**
- **[X] The application maintains its frame rate but substantially increases energy consumption.  →  Probably an issue**
- **[X] The application maintains its frame rate by noticeably reducing visual quality.  →  Unsure / depends**
#### Q14. Suppose the same measured frame-time degradation occurs in the following situations. Would its severity differ?

Situation A: The user is standing still and reading a menu.

Situation B: The user is moving their head rapidly while manipulating an object.

- Much more severe in A
- Somewhat more severe in A
- About equally severe
- Somewhat more severe in B
- **[X] Much more severe in B**
- It depends
- Unsure
#### Q15. To what extent do you agree with the following statement?

The same measured performance degradation can constitute a performance issue in one XR usage context but not in another.

- Strongly disagree
- Disagree
- Neither agree nor disagree
- Agree
- **[X] Strongly agree**
#### Q16. Which contextual factors should be considered when defining an XR performance requirement?

Select all that apply.

- **[X] Device or hardware class**
- **[X] Display refresh rate**
- **[X] Application type**
- **[X] Scene complexity**
- **[X] User motion**
- **[X] User interaction**
- **[X] Session duration**
- **[X] Thermal state**
- **[X] Battery state**
- **[X] Rendering quality**
- **[X] Application task**
- User population
- **[X] Accessibility or comfort considerations**
- Other: _______
#### Q17. In your experience, are fixed performance thresholds sufficient for determining whether an XR application has a performance issue?

- Yes, in most cases
- Yes, but only for some metrics
- **[X] No, thresholds usually need contextual information**
- No, thresholds alone are rarely meaningful
- Unsure
#### Q18. Please briefly explain your answer to Q17.

Open response:

- **[X] Fixed thresholds (for example 13.9 ms at 72 Hz or 11.1 ms at 90 Hz) are a useful starting contract, but the same millisecond spike is not equally an issue while a user is reading a menu versus turning their head quickly in a dense scene. Mobile AR also has thermal and battery context that a single frame-time number cannot capture. I treat thresholds as necessary but not sufficient: perceptibility, comfort, task, device, and session length decide whether a miss is a defect.**
### Section C. Performance Tradeoffs

#### Q19. How acceptable would each of the following tradeoffs generally be if it allowed an XR application to satisfy an important timing or responsiveness requirement?

1 = Never acceptable
2 = Usually unacceptable
3 = Depends on context
4 = Usually acceptable
5 = Highly acceptable

- **[X] Reducing texture resolution  →  4 Usually acceptable**
- **[X] Reducing shadow quality  →  4 Usually acceptable**
- **[X] Reducing object detail / level of detail  →  4 Usually acceptable**
- **[X] Reducing animation quality  →  3 Depends on context**
- **[X] Reducing model complexity  →  3 Depends on context**
- **[X] Reducing the frequency of some computations  →  3 Depends on context**
- **[X] Increasing memory use  →  3 Depends on context**
- **[X] Increasing energy consumption  →  2 Usually unacceptable**
- **[X] Increasing battery drain  →  2 Usually unacceptable**
- **[X] Slightly increasing latency elsewhere in the application  →  3 Depends on context**
#### Q20. What information would you need before deciding whether a performance tradeoff is acceptable?

Select all that apply.

- **[X] Magnitude of performance improvement**
- **[X] Magnitude of quality degradation**
- **[X] User-visible effects**
- **[X] Application domain**
- **[X] Task being performed**
- **[X] Duration of the degradation**
- **[X] Device type**
- **[X] Energy impact**
- **[X] Thermal impact**
- **[X] Accessibility or comfort implications**
- Other: _______
#### Q21. Describe a performance tradeoff that you have considered or encountered in an XR project.

Open response:

- **[X] On a standalone Unity VR scene we dropped shadow cascades and tightened LOD / occlusion so the headset stayed at 72 FPS, at the cost of flatter lighting and simpler distant geometry. On mobile AR we lowered the AR camera resolution and disabled some real-time lighting so tracking and UI stayed responsive, accepting softer passthrough and less detailed virtual overlays. Both tradeoffs were acceptable only because the task did not depend on fine visual discrimination; we would not have made the same cuts in a precision-placement task.**
## RQ2. What challenges do XR developers face in reproducing, validating, and evaluating XR performance issues?

### Section D. Current Performance-Debugging Practice

#### Q22. How often do you encounter XR performance issues that are difficult to reproduce?

- Never
- Rarely
- Sometimes
- **[X] Often**
- Very often
#### Q23. How often does reproducing an XR performance issue require recreating a specific combination of the following?

1 = Never
2 = Rarely
3 = Sometimes
4 = Often
5 = Very often

- **[X] Scene or location  →  4 Often**
- **[X] Viewpoint  →  4 Often**
- **[X] Head movement  →  5 Very often**
- **[X] Hand or controller movement  →  4 Often**
- **[X] Interaction sequence  →  5 Very often**
- **[X] Number or type of objects  →  4 Often**
- **[X] Application state  →  4 Often**
- **[X] Device model  →  4 Often**
- **[X] Device temperature  →  5 Very often**
- **[X] Length of execution  →  4 Often**
- **[X] Network or external conditions  →  3 Sometimes**
#### Q24. When you receive a report of an XR performance problem, how often does the report contain enough information to reproduce the issue?

- Never
- **[X] Rarely**
- Sometimes
- Often
- Almost always
#### Q25. What information is most commonly missing from XR performance-issue reports?

Select all that apply.

- **[X] Exact user actions**
- **[X] User movement / trajectory**
- **[X] Scene state**
- Device model
- Software version
- **[X] Refresh rate or device configuration**
- **[X] Performance measurements**
- Expected performance requirement
- **[X] Thermal state**
- **[X] Session duration**
- **[X] Reproduction steps**
- Visual evidence
- **[X] Profiling data**
- Other: _______
#### Q26. How difficult are the following activities in your current XR development process?

1 = Very easy
2 = Easy
3 = Neither easy nor difficult
4 = Difficult
5 = Very difficult

- **[X] Reproducing a reported performance issue  →  4 Difficult**
- **[X] Determining the conditions that trigger an issue  →  4 Difficult**
- **[X] Determining whether an observed slowdown is abnormal  →  4 Difficult**
- **[X] Separating real degradation from measurement noise  →  4 Difficult**
- **[X] Identifying the responsible subsystem  →  4 Difficult**
- **[X] Identifying the responsible source code  →  5 Very difficult**
- **[X] Determining whether an optimization actually fixed the issue  →  4 Difficult**
- **[X] Determining whether the fix introduced another performance problem  →  4 Difficult**
- **[X] Rechecking the issue on another device  →  4 Difficult**
- **[X] Rechecking the issue after a software change  →  3 Neither easy nor difficult**
#### Q27. Which tools or techniques do you currently use when investigating XR performance issues?

Select all that apply.

- **[X] Engine profiler**
- **[X] CPU profiler**
- **[X] GPU profiler**
- **[X] Frame-time monitoring**
- Device performance APIs
- **[X] Logging**
- **[X] Manual observation**
- **[X] User reports**
- **[X] Recorded videos**
- Automated tests
- Custom benchmarks
- **[X] Repeated manual execution**
- Performance regression tests
- **[X] Other: Unity XR stats / Oculus Metrics Tool, browser performance panel for A-Frame**
#### Q28. How do you usually reproduce a performance issue once it has been identified?

Select all that apply.

- **[X] Manually repeat the reported actions**
- **[X] Follow written reproduction steps**
- Replay recorded interactions
- Use an automated test
- Use a benchmark workload
- Create a custom script
- **[X] Recreate the scene manually**
- I generally cannot reliably replay performance issues
- Other: _______
#### Q29. Do you currently maintain reusable workloads, scenarios, or tests for XR performance problems?

- Yes, systematically
- Yes, for some important problems
- **[X] Rarely**
- No
- Unsure
#### Q30. After a performance fix is implemented, how do you normally determine whether it worked?

Select all that apply.

- **[X] Developer judgment**
- **[X] User-visible observation**
- **[X] Profiling before and after the fix**
- **[X] Compare performance metrics against a threshold**
- **[X] Compare against the previous version**
- **[X] Replay the original triggering scenario**
- Automated regression test
- **[X] Test on multiple devices**
- User testing
- Other: _______
#### Q31. How confident are you that your current process distinguishes a true XR performance defect from normal run-to-run performance variability?

- Not at all confident
- Slightly confident
- **[X] Moderately confident**
- Very confident
- Extremely confident
#### Q32. How confident are you that a performance fix accepted by your current process will remain effective when the same workload is repeated?

Use the same five-point confidence scale.

- **[X] Answer: Moderately confident**
#### Q33. Think about the most recent difficult XR performance problem you encountered. What made it difficult to reproduce, diagnose, or validate?

Open response:

- **[X] The worst case was a hitch that appeared only after about 10–15 minutes, once the phone or headset was warm, and only when the user turned quickly in a dense scene with several spawned objects. Editor play mode stayed smooth. The Unity profiler on-device did not make the thermal throttle obvious, and written reproduction steps never captured the head-motion path. We could not tell whether a later patch fixed it without repeating the full warm-up session on the same device.**
## RQ3. What information and capabilities would make a shared XR performance benchmark useful for development and research?

### Section E. Current Benchmark Use

#### Q34. Have you used an XR or software-performance benchmark before?

- **[X] Yes**
- No
- Unsure
#### Q35. If yes, what did you use the benchmark for?

Select all that apply.

- Comparing systems or devices
- **[X] Comparing software versions**
- **[X] Evaluating performance**
- Evaluating testing techniques
- **[X] Evaluating optimization techniques**
- Performance regression testing
- **[X] Research evaluation**
- Teaching / training
- Other: _______
#### Q36. How satisfied are you with currently available resources for evaluating XR performance-testing and optimization techniques?

- Very dissatisfied
- **[X] Dissatisfied**
- Neither satisfied nor dissatisfied
- Satisfied
- Very satisfied
- I am not aware of such resources
#### Q37. To what extent do you agree with the following statement?

The XR community would benefit from a shared dataset of real and controlled performance issues that can be reliably reproduced and measured.

- Strongly disagree
- Disagree
- Neither agree nor disagree
- Agree
- **[X] Strongly agree**
### Section F. Desired Benchmark Properties

#### Q38. Suppose a shared XR performance benchmark contained known performance issues. How important would each of the following pieces of information be?

1 = Not important
2 = Slightly important
3 = Moderately important
4 = Very important
5 = Essential

- **[X] Application and version  →  4 Very important**
- **[X] Device class  →  5 Essential**
- **[X] Performance requirement  →  4 Very important**
- **[X] Performance metric being violated  →  5 Essential**
- **[X] Workload that triggers the issue  →  5 Essential**
- **[X] Exact interaction sequence  →  5 Essential**
- **[X] User-motion trajectory  →  4 Very important**
- **[X] Scene / environmental conditions  →  4 Very important**
- **[X] Matched non-failing comparison workload  →  5 Essential**
- **[X] Raw performance measurements  →  5 Essential**
- **[X] Summary performance statistics  →  4 Very important**
- **[X] Thermal state  →  4 Very important**
- **[X] Reproduction instructions  →  5 Essential**
- **[X] Evidence that the issue reproduces across repeated executions  →  5 Essential**
- **[X] Evidence that it reproduces across devices  →  4 Very important**
- **[X] Localization to a subsystem  →  4 Very important**
- **[X] Localization to source code  →  3 Moderately important**
- **[X] Known developer fix  →  4 Very important**
- **[X] Evidence that the fix removes the issue  →  5 Essential**
- **[X] Provenance of the issue  →  3 Moderately important**
- **[X] Issue severity  →  4 Very important**
#### Q39. Which FIVE pieces of information from Q38 would be most important to you?

Select up to five.

- **[X] Answer: (1) Workload that triggers the issue; (2) Exact interaction sequence; (3) Raw performance measurements; (4) Reproduction instructions; (5) Evidence that the fix removes the issue.**
#### Q40. How important would each of the following benchmark properties be?

Use the same 1–5 scale.

- **[X] Issues drawn from real XR projects  →  5 Essential**
- **[X] Controlled / intentionally injected issues  →  4 Very important**
- **[X] Multiple XR applications  →  5 Essential**
- **[X] Multiple engines  →  4 Very important**
- **[X] Multiple device classes  →  5 Essential**
- **[X] Multiple performance-problem types  →  5 Essential**
- **[X] Reproducible workloads  →  5 Essential**
- **[X] Standard performance requirements  →  4 Very important**
- **[X] Measured ground truth  →  5 Essential**
- **[X] Known fixes  →  4 Very important**
- **[X] Repeated measurements  →  5 Essential**
- **[X] Cross-device validation  →  4 Very important**
- **[X] Open access  →  5 Essential**
- **[X] Ability for outside developers to contribute new benchmark entries  →  4 Very important**
- **[X] Versioning as platforms and hardware evolve  →  5 Essential**
#### Q41. How useful would such a benchmark be for each of the following activities?

1 = Not useful
2 = Slightly useful
3 = Moderately useful
4 = Very useful
5 = Extremely useful

- **[X] Reproducing known XR performance problems  →  5 Extremely useful**
- **[X] Evaluating performance-testing tools  →  4 Very useful**
- **[X] Evaluating workload-generation techniques  →  4 Very useful**
- **[X] Evaluating performance-issue localization  →  4 Very useful**
- **[X] Evaluating automated repair techniques  →  3 Moderately useful**
- **[X] Comparing performance tools  →  4 Very useful**
- **[X] Comparing software versions  →  4 Very useful**
- **[X] Performance regression testing  →  5 Extremely useful**
- **[X] Training developers  →  4 Very useful**
- **[X] Teaching XR development  →  4 Very useful**
- **[X] Reproducing research studies  →  4 Very useful**
- **[X] Establishing common ground truth for research evaluation  →  5 Extremely useful**
#### Q42. Which THREE uses would be most valuable to you?

Select up to three.

- **[X] Answer: (1) Reproducing known XR performance problems; (2) Performance regression testing; (3) Establishing common ground truth for research evaluation.**
#### Q43. Would you be more likely to trust a benchmark entry if the performance issue had been confirmed through repeated on-device measurement rather than labeled only through manual inspection?

- Much less likely
- Somewhat less likely
- No difference
- Somewhat more likely
- **[X] Much more likely**
- Unsure
#### Q44. Would attaching a replayable workload that reliably triggers the performance issue make a benchmark entry more useful to you?

- Not at all
- Slightly
- Moderately
- Substantially
- **[X] Extremely**
#### Q45. Would having both a workload that triggers the issue and a closely matched workload that does not trigger it make the benchmark more useful for evaluating performance problems?

- Not at all
- Slightly
- Moderately
- Substantially
- **[X] Extremely**
- Unsure
#### Q46. How important is it that benchmark entries include performance issues that existing tools fail to detect?

- Not important
- Slightly important
- Moderately important
- **[X] Very important**
- Essential
#### Q47. How important is it that the benchmark contain performance issues of different difficulty levels?

Use the same 1–5 scale.

- **[X] Answer: 4 — Very important**
#### Q48. How likely would you be to use a publicly available benchmark containing reproducible XR performance issues?

- Very unlikely
- Unlikely
- Unsure
- Likely
- **[X] Very likely**
#### Q49. For which purposes would you personally consider using such a benchmark?

Select all that apply.

- **[X] Development**
- **[X] Performance debugging**
- **[X] Regression testing**
- Tool development
- **[X] Research**
- **[X] Teaching**
- **[X] Training**
- Device evaluation
- I would probably not use it
- Other: _______
#### Q50. What would prevent you from using or trusting such a benchmark?

Select all that apply.

- **[X] Applications are unrealistic**
- **[X] Workloads are unrealistic**
- **[X] Hardware does not match mine**
- Performance thresholds do not match my application
- **[X] Issues are too artificial**
- **[X] Benchmark becomes outdated**
- **[X] Difficult setup**
- High execution cost
- **[X] Unclear ground truth**
- **[X] Insufficient reproduction information**
- **[X] Lack of representative applications**
- Other: _______
#### Q51. What would make a shared XR performance benchmark valuable enough for you to use in practice?

Open response:

- **[X] Replayable interaction traces (head, hands, and camera) plus a known-good and known-bad pair for the same scene. Coverage of standalone VR, mobile AR, and at least one head-mounted MR device. Thermal and session-duration metadata. Open Unity and A-Frame scenes so I can run the workload myself. Clear frame-time / comfort requirements per device class, repeated-run evidence, and a short note of the developer fix when one exists.**
#### Q52. Is there any important aspect of XR performance testing or benchmarking that we have not asked about?

Open response:

- **[X] Comfort and cybersickness should be first-class outcomes, not only frame rate. Passthrough delay and tracking quality matter as much as GPU time in AR/MR. Shader warmup, asset streaming, and OS thermal policy often cause issues that profilers attribute to 'the scene.' WebXR / A-Frame paths also behave differently from native Unity on the same headset, so a benchmark that is engine-only will miss a large part of current XR work.**
