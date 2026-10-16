# RFID-Based Vehicle Access and Security Management System — Project Proposal

Oct 16, 2026 · @Otieno

## Title Page

**\[University of Nairobi\]** **\[Faculty / School of Computing and Informatics\]**

**Gatelock: An RFID-Based Vehicle Access, Parking and Security Management System**

By **\[Your Full Name\]** Registration Number: **\[P15/XXXXX/20XX\]** Supervised by **\[Supervisor's Name\]**

October 2026

This project proposal has been submitted in partial fulfilment of the requirements of the Bachelor of Science in **\[Computer Science\]** as offered by the **\[University Name\]**.

*"Gatelock" is a working name. Replace every item in square brackets before submission.*

## Table of Contents

1. Chapter 1: Introduction
   1. Background
   2. Problem Statement
   3. Objectives (Research Objectives, System Objectives)
   4. Project Justification
   5. Scope
   6. Assumptions
2. Chapter 2: Literature Review
   1. RFID Technologies
   2. RFID in Vehicle Access Control
   3. Access-Control Models and Algorithms
   4. Real-Time Event Processing
   5. Security of RFID Systems
   6. Parking Occupancy Detection
   7. Implications of Literature Review
3. Chapter 3: Methodology
   1. System Development Methodology
   2. Technologies
   3. Project Schedule
   4. Budget
4. References

**List of Tables**

Table 1: Budget

Table 2: Roles and Parking Zones

**List of Figures**

Figure 1: System Architecture

Figure 2: Gate-to-Parking Flow

Figure 3: Dashboard Parking Map

Figure 4: Gantt Chart

## Chapter 1: Introduction

### 1.1 Background

Controlled vehicle access points are found at university campuses, gated estates, hospitals, office parks, industrial sites and government facilities. At most Kenyan institutions, access at these points is still managed manually. A guard stops each vehicle, inspects a sticker or pass, and writes the registration number, driver's name and time into a paper logbook.

This manual process has three weaknesses. First, it is slow: every vehicle must stop, and queues form at peak hours such as the morning arrival and evening departure. Second, it is unreliable: paper stickers are easily photocopied or transferred between vehicles, and verification depends on the alertness and integrity of the guard on duty. Third, it produces almost no usable data: logbooks are rarely complete, are hard to search after an incident, and cannot alert anyone in real time when an unauthorised or flagged vehicle appears.

Radio Frequency Identification (RFID) offers an alternative. An RFID tag attached to a vehicle carries a unique identifier that a reader can capture without line of sight and without the vehicle stopping. RFID is already widely used for toll collection, logistics and parking. Its cost has fallen to a level where a small institution can deploy it.

RFID alone only identifies a tag. To be useful for security, the identification must be combined with an embedded controller at the gate, an access-control engine that decides who may enter and when, real-time event processing that raises alerts, and a management dashboard. This proposal is for the development of such an integrated system.

Access control is closely tied to parking. Institutions typically reserve some parking for senior staff and guests of honour, give general parking to staff, and set aside space for visitors and delivery vehicles. When these areas are managed by hand, VIP bays are taken by other vehicles, and drivers circle looking for a free space. The gate keeps admitting vehicles after the car park is full, because the guard has no view of how many spaces remain. Linking the gate to live parking occupancy solves both problems: the system can direct each vehicle to a space in the right area, and stop admitting vehicles to an area that is full.

### 1.2 Problem Statement

Institutions that control vehicle access rely on manual checks and paper logs that are slow, easy to defeat with forged or shared passes, and provide no real-time visibility or reliable audit trail. Commercial automated access-control systems exist but are costly, often closed, and are not tailored to the time-based and role-based access rules that institutions need. Parking is also unmanaged: reserved areas are taken by the wrong vehicles, and vehicles are admitted even when no space is left. There is therefore a need for an affordable, secure RFID-based system that identifies vehicles automatically, enforces configurable access policies, allocates parking by vehicle category, refuses entry when an area is full, detects suspicious activity in real time and gives administrators a clear management dashboard with a live parking map.

### 1.3 Objectives

#### 1.3.1 Research Objectives

(i) **To investigate RFID technologies suitable for vehicle identification.** The system's read range, speed and cost depend on the RFID frequency band and tag type chosen. This objective compares low-frequency (LF), high-frequency (HF) and ultra-high-frequency (UHF) RFID to select an appropriate technology for the prototype and for a full-scale deployment.

(ii) **To investigate access-control models and decision algorithms.** A gate must decide in under a second whether a vehicle may pass. This objective reviews access-control models such as role-based access control (RBAC) and rule-based approaches, and techniques such as time windows and anti-passback, to design the system's decision engine.

(iii) **To investigate real-time event processing and anomaly detection approaches.** This objective identifies how access events can be processed as they happen so that suspicious patterns, such as repeated denied attempts or the same tag appearing at two gates within an impossible time, raise alerts immediately.

(iv) **To investigate security threats to RFID systems and their countermeasures.** RFID tags can be cloned, eavesdropped on and replayed. This objective reviews these attacks and the cryptographic and architectural defences that mitigate them.

(v) **To investigate parking occupancy detection methods.** To know whether each numbered parking lot is free or occupied, the system needs a sensor at every lot. This objective compares occupancy sensing technologies, such as infrared, ultrasonic and magnetic sensors, on accuracy, cost and suitability for indoor and outdoor parking.

#### 1.3.2 System Objectives

To develop an RFID-based vehicle access system that will:

(i) Use RFID readers and an embedded controller to identify vehicles and operate a barrier at an access point in real time.

(ii) Assign every vehicle a role (VIP, staff, or visitor and delivery) and enforce access policies based on that role, time of day and pass validity, including anti-passback. Unregistered vehicles are registered at a separate lane with the driver's name and ID number, and issued a temporary tag that is deactivated when it is returned at exit.

(iii) Allocate each admitted vehicle a numbered lot in the parking zone that matches its role, show the lot number to the driver at the gate, and refuse entry with an alert when that zone is full.

(iv) Detect the occupancy of every parking lot with a sensor and display all three zones on a live parking map, with each lot shown as open, occupied or reserved.

(v) Log every access event and raise real-time alerts for blacklisted vehicles and anomalous access patterns.

(vi) Provide a web-based dashboard for registering vehicles, managing passes and rules, monitoring live gate activity and generating reports.

(vii) Secure communication between the gate controller and the server, and continue to operate at the gate when the network is unavailable.

### 1.4 Project Justification

Vehicles that enter a compound unchecked pose a direct security risk to people and property. Automated identification removes the dependence on a guard's judgement for routine entries and frees security staff to focus on exceptions, such as visitors and flagged vehicles.

The system also reduces congestion. Because UHF RFID can read a tag as a vehicle approaches, authorised vehicles need not stop for a manual check. This shortens queues at peak hours.

Finally, the system creates a reliable, searchable record of every entry and exit. After an incident, administrators can establish which vehicles were on site and when. Over time, the same data reveals traffic patterns that support decisions on staffing, parking and gate opening hours.

### 1.5 Scope

(i) The system will be developed and demonstrated for a single institutional use case, such as a university campus, with one entry gate, split into an express lane for tagged vehicles and a registration lane for unregistered vehicles, and three parking zones: VIP, staff, and visitors and deliveries. Each zone has numbered lots.

(ii) The hardware will be a working scale prototype, with a servo-driven model barrier and a model car park, rather than a full installation on a real gate.

(iii) Vehicle identification will rely on RFID only. Automatic number-plate recognition (ANPR) is identified as future work.

(iv) Anomaly detection will use rule-based techniques. Machine-learning-based detection is outside the scope of this project.

### 1.6 Assumptions

The following assumptions are held as true in the development of this system:

(i) Each registered vehicle carries exactly one tag, fixed to the vehicle so that it cannot easily be removed without damage.

(ii) Vehicles approach the reader one at a time, in a single lane.

(iii) The gate site has mains power and a WiFi or wired network connection, with occasional outages.

(iv) Every vehicle belongs to exactly one role. Unregistered vehicles, such as visitors and deliveries, use the registration lane, where the driver's name and national ID number are recorded and a temporary windscreen tag is issued. The tag is returned at exit.

(v) Each lot holds one vehicle. A lot sensor detects whether a vehicle is present, but not which vehicle it is.

## Chapter 2: Literature Review

### 2.1 RFID Technologies

Want (2006) describes RFID as automatic identification at a distance that, unlike bar codes, needs no line of sight. He divides tags into active tags, which carry a battery, and passive tags, which draw power from the reader's field. Passive tags are cheap and long-lived, which makes them the usual choice for identifying large numbers of items or vehicles.

Want further separates passive RFID into near-field and far-field designs. Near-field systems, which include the 125 kHz (LF) and 13.56 MHz (HF) bands, couple the tag and reader magnetically and work over short distances. Far-field systems in the UHF band (860–960 MHz) reflect the reader's signal back and achieve read ranges of several metres. HF smart cards follow the ISO 14443 proximity-card standard, while UHF tags typically follow the EPC Gen2 standard.

For vehicle access, read range is decisive. A driver cannot be expected to hold a card a few centimetres from a reader, so production systems use UHF windshield tags. HF readers such as the RC522 module remain useful for low-cost prototyping because they are cheap and well supported on microcontrollers.

### 2.2 RFID in Vehicle Access Control

RFID vehicle access systems have been studied in several settings. Mohandes et al. (2016) built a hybrid system to control vehicle entry to Makkah during the Hajj season. Authorised vehicles received passive RFID tags carrying their permitted entry schedule, and vehicles without tags were identified by automatic licence plate recognition (ALPR). In tests over two seasons, the RFID subsystem identified every passing vehicle at speeds of up to 100 km/h, while ALPR recognised about 94% of untagged vehicles.

Closer to the Kenyan context, Chazanga, Phiri and Namukolo (2019) developed a two-factor vehicle access system for the University of Zambia. Their baseline survey found that the campus relied on windscreen stickers, staff identity cards and handwritten logbooks, and that respondents were concerned about vehicle theft on campus. Their prototype combined an RFID card reader with number plate recognition and a boom gate. It offered five configurable authentication states, ranging from logging only, through RFID-only or plate-only, to requiring both factors together. Access records were first written to a text log over a serial connection, with a MySQL database added for demonstration.

Masri and Ab. Aziz (2025) report a similar web-based RFID vehicle access and monitoring system for the main campus of Universiti Tun Hussein Onn Malaysia. They developed it with an object-oriented design and a prototyping model. Their stated aims were to reduce human error, shorten waiting times at entry points and improve the accuracy of security records. They propose statistical analysis of access data as future work.

A European patent (EP 2230624 A1) describes a UHF RFID access system that places a set of antennas on each side of a barrier. By noting which antenna set reads a tag first, the system determines whether the vehicle is moving inward or outward. It does not record an entry or exit if the vehicle turns back. This direction-sensing approach is the basis of anti-passback enforcement.

### 2.3 Access-Control Models and Algorithms

Sandhu et al. (1996) introduced a family of role-based access control (RBAC) reference models. In RBAC, permissions are attached to roles and users are assigned to roles, rather than permissions being granted to users one by one. This simplifies administration when many users share the same access needs, as staff, students, visitors and contractors do at a campus gate.

Plain RBAC does not express time. Bertino, Bonatti and Ferrari (2001) extended it with Temporal RBAC (TRBAC), in which roles can be enabled and disabled periodically, for example only during working hours. TRBAC also supports role triggers that enable or disable roles in response to other events, and it checks that specifications are free of ambiguity. Time-bound rules of this kind map directly to vehicle access needs, such as visitor passes valid only between 08:00 and 18:00.

### 2.4 Real-Time Event Processing

Cugola and Margara (2012) survey what they call information flow processing systems: tools that process continuous streams of information as they arrive, according to pre-deployed rules. They distinguish data stream processing, which filters and aggregates streams, from complex event processing (CEP), which detects patterns made up of several related events.

RFID is a common application of CEP. Wang et al. (2006) note that raw RFID readings contain duplicates, carry implicit meaning and arrive in high volume, so they must be cleaned and interpreted on the fly. They formalise RFID events and rules and build a detection engine for events with tight time constraints, showing that conventional event–condition–action engines handle these poorly. Wu, Diao and Rizvi (2006) present SASE, a CEP system that runs pattern queries over real-time streams of RFID readings, with surveillance and facility management among its target uses.

For transport between devices and the server, MQTT is widely used in IoT systems. Silva et al. (2021) compared MQTT, CoAP and OPC UA on local and large-scale testbeds. They found that no single protocol performed best in every scenario, with CoAP achieving the lowest completion time across their tests.

### 2.5 Security of RFID Systems

Juels (2006) surveys RFID security and privacy research. He identifies cloning and counterfeiting as central threats, because a basic tag simply broadcasts a fixed identifier that an attacker can read and copy. He also notes that low-cost tags have very limited resources, so standard cryptographic tools cannot always be used.

Even tags that do use cryptography can be weak. De Koning Gans, Hoepman and Garcia (2008) showed a practical, low-cost attack on the MIFARE Classic, then the most widely used contactless smart card. A weakness in its random number generator let them recover keystream from the proprietary CRYPTO1 cipher, read memory blocks and modify them. Garcia et al. (2008) went further: they reverse-engineered CRYPTO1 and demonstrated attacks that recover the card's secret key. These findings mean that an access system relying on MIFARE Classic, or on a tag's plain identifier, should assume that tags can be cloned.

### 2.6 Parking Occupancy Detection

Fahim, Hasan and Chowdhury (2021) reviewed smart parking systems and grouped them by sensing technology, including infrared (IR), ultrasonic, magnetometer, inductive loop, camera and RFID sensors. They found ultrasonic sensors cheap and easy to maintain, and best suited to covered parking where a sensor is mounted above each bay. IR sensors are also common, but they are affected by rain and so suit indoor use. Magnetometers buried under each bay are unaffected by weather and work indoors or outdoors. Cameras cover many bays at once but cost more and are affected by shadows and changing light.

Several of the systems they review combine RFID at the entrance, for gate management, with an occupancy sensor at each lot that reports to a web or mobile application. Lin, Rivano and Le Mouël (2017) organise smart parking research into three themes: collecting information about spaces, deploying the system, and delivering the information to users. In those terms, this project's lot sensors collect the information, and the gate display and dashboard parking map deliver it.

### 2.7 Implications of Literature Review

The reviewed systems confirm that RFID vehicle access control is feasible and effective. Mohandes et al. (2016) show that UHF tags can be read reliably at road speeds. Chazanga, Phiri and Namukolo (2019) and Masri and Ab. Aziz (2025) show that campus deployments reduce queuing and human error. However, these systems share four gaps that this project addresses.

First, their access logic is simple. Access is granted if a tag or plate is on a list, sometimes combined with a fixed schedule. None of them applies a formal model such as RBAC, nor the time-based roles that TRBAC describes. The proposed system will use role-based policies with time windows and validity periods, informed by Sandhu et al. (1996) and Bertino, Bonatti and Ferrari (2001).

Second, they record events for later review rather than analysing them as they happen. The UNZA system wrote records to a text log, and statistical analysis remains future work in the UTHM system. The proposed system will apply complex event processing, following Wang et al. (2006) and Cugola and Margara (2012), to raise alerts as suspicious patterns occur. Examples are repeated denied attempts, use of a blacklisted tag, and the same tag read at two gates within an impossibly short time.

Third, they give little attention to tag cloning. Juels (2006), de Koning Gans, Hoepman and Garcia (2008) and Garcia et al. (2008) show that plain identifiers and MIFARE Classic cards can be copied. The proposed system will therefore avoid MIFARE Classic, enforce anti-passback (EP 2230624 A1) so that a cloned tag in use is detected, and encrypt all gate-to-server communication. Dual-factor verification with number plate recognition, as in Mohandes et al. (2016) and Chazanga, Phiri and Namukolo (2019), is identified as future work.

Fourth, they treat the gate and the car park separately. The access systems decide whether a vehicle may enter, but not whether there is space for it. The parking systems reviewed by Fahim, Hasan and Chowdhury (2021) report which lots are free, but they do not link occupancy to role-based admission. The proposed system joins the two: a vehicle's role sets its parking zone, and that zone's live occupancy decides whether the gate opens and which lot is assigned. Event processing will also compare reservations with sensor readings. It will raise an alert when a lot becomes occupied without a reservation, and release a reserved lot that stays empty too long.

## Chapter 3: Methodology

### 3.1 System Development Methodology

Before selecting a development methodology, the system was broken into its main components based on the system objectives. Five components were identified:

(i) **Gate controller:** an embedded device at the access point that reads RFID tags, operates the barrier and gives the driver visual feedback.

(ii) **Access-control and event-processing backend:** a server that stores vehicles, tags and rules, decides whether each read is granted or denied, logs every event and detects suspicious patterns.

(iii) **Management dashboard:** a web application used by security staff and administrators to register vehicles, manage passes and rules, watch live gate activity, respond to alerts and generate reports.

(iv) **Message broker:** the communication layer that carries tag reads from the gate controller to the backend and decisions back to the gate.

(v) **Parking sensor node:** an embedded device with an occupancy sensor at every numbered lot in the three parking zones, which reports each change in lot status to the backend.

&#91;embedded content: Figure 1: System architecture · 4 components\]

The gate controller sends each tag read through the MQTT broker to the backend, which returns a grant or deny decision and pushes the event live to the dashboard. The parking node reports every change in lot status through the same broker.

Each vehicle's role decides which zone it may park in. Table 2 shows the three roles and their zones.

| Role | Parking zone | Lot numbers | Tag issued |
| --- | --- | --- | --- |
| VIP | Zone A: VIP | A1, A2, … | Permanent |
| Staff | Zone B: Staff | B1, B2, … | Permanent |
| Visitor or delivery | Zone C: Visitors and deliveries | C1, C2, … | Temporary, issued at the registration lane, returned at exit |

Table 2: Roles and parking zones

When a tag is read, the backend checks the vehicle's role, finds a free lot in its zone and reserves it. The gate opens and shows the driver the lot number. If the zone has no free lot, the gate stays closed, tells the driver the zone is full, and alerts the dashboard.

The gate has two lanes. In the **express lane**, vehicles with a registered tag queue at the barrier, and the barrier opens as soon as a valid tag is read. Vehicles without a tag use the **registration lane**. There, the guard records the driver's name and national ID number on the dashboard, scans a temporary tag at a desk reader to link it to that record, and hands the tag over for the windscreen. From then on, the temporary tag works like any other: it is assigned a lot in Zone C and is checked by the same rules.

When the vehicle leaves, the temporary tag is handed back and deactivated, and its lot is released. Event processing will raise an alert if a temporary tag is read at the exit but not returned, or is still active long after the visitor's expected departure. Because national ID numbers are personal data under Kenya's Data Protection Act, 2019 (Kenya, 2019), the system will store only the fields it needs, encrypt them, and delete visitor records after a set retention period.

&#91;embedded content: Figure 2: Gate-to-parking flow · 2 checks, 3 outcomes\]

A lot is reserved, and shown red, as soon as the gate opens. If its sensor does not detect a vehicle within a set time, the reservation is released and the lot turns green again.

Based on this analysis, the **spiral model** was selected. The spiral model couples the iterative nature of prototyping with the controlled and systematic aspects of the waterfall model (Pressman, 2010). Each cycle passes through requirement specification, design, implementation and testing, and ends with a risk review before the next cycle begins.

The spiral model suits this project for two reasons. First, the components depend on each other in sequence: the backend cannot be tested without tag reads from the gate controller, and the dashboard needs the backend's events. Each component can therefore be built as its own cycle. Second, the project carries technical risks, such as RFID read reliability and the response time of the full loop, that are best discovered early. The risk review at the end of each cycle allows the design to change before later work depends on it.

To reduce the burden of integration, each component will be developed together with the part of the backend it uses. The four cycles are described below.

(i) **Cycle 1: Gate controller hardware.** Requirement specification will define the read range, response time and feedback required at the gate. A short needs-finding exercise with campus security staff will establish how vehicles are currently checked. The hardware and its wiring will then be designed, implemented and tested, together with the backend endpoints that receive tag reads and lot status updates. The parking sensor node, with a sensor at each numbered lot, will be built and tested in the same cycle.

(ii) **Cycle 2: Access-control engine and event processing.** Requirement specification will capture the institution's access policies: vehicle categories, gates, time windows, pass validity, anti-passback, the mapping of roles to parking zones, and lot allocation. The data model and rules engine will be designed and implemented. The event-processing rules for alerts will follow. Testing will confirm that every policy produces the correct decision within the target response time.

(iii) **Cycle 3: Management dashboard.** Requirement specification will draw on interviews with security staff and administrators, the target users. The interface and its backend endpoints will be designed, implemented and tested together with the live gate, to confirm that gate events and lot status changes, including those on the live parking map, appear on the dashboard with minimal delay.

(iv) **Cycle 4: Security hardening.** The threats identified in Section 2.5 will be modelled. Countermeasures will be implemented: encrypted MQTT, device authentication, secure tags, hashed passwords, role-based dashboard access, audit logging, and encryption and timed deletion of visitors' ID numbers. Testing will include attempted tag cloning, replay of captured messages and operation of the gate during a network outage.

### 3.2 Technologies

(i) **Hardware**

The gate controller will be built on the ESP32 microcontroller, chosen for its built-in WiFi, low cost and wide library support. Tags will be read with an RC522 13.56 MHz reader for the prototype, using cards that support AES authentication, such as MIFARE DESFire EV2 or NTAG 424 DNA, rather than MIFARE Classic. If the budget allows, a short-range UHF module will be added to demonstrate the read range of a real vehicle installation. A servo motor will drive a scale model barrier. An ultrasonic sensor will detect an approaching vehicle, and an OLED screen and LEDs will show the decision. The firmware will be written in C++ using the Arduino framework, and will cache a local whitelist so the gate keeps working when the network is down.

A second ESP32 will act as the parking sensor node. In the scale model, each zone will have four numbered lots, giving twelve lots in total. Each lot will have an IR obstacle sensor, which needs only one input pin, so one ESP32 can monitor all twelve. For a full-size covered car park, the review by Fahim, Hasan and Chowdhury (2021) points to ultrasonic sensors mounted above each bay; for an open car park, it points to magnetometers under each bay. The node will publish a message only when a lot changes state, and will ignore brief changes, such as a person walking past, by requiring a reading to hold for a few seconds.

The registration lane will have its own model barrier, and a second RC522 reader at the guard's desk. The guard uses this reader to link a temporary tag to the visitor's record before handing it over, and to deactivate the tag when it is returned.

(ii) **Communication**

The gate controller and backend will communicate over MQTT using the Eclipse Mosquitto broker, secured with TLS. MQTT was chosen because its publish–subscribe model lets several gates and the dashboard share the same event stream, and because it is lightweight enough for a microcontroller.

(iii) **Backend**

The backend will be written in Python using the FastAPI framework, with a PostgreSQL database. FastAPI was chosen because it supports asynchronous processing, which suits a server that must handle MQTT messages and WebSocket connections at the same time. The access-control engine will implement role-based policies with time windows, and the event-processing module will apply pattern rules to the stream of access events to raise alerts.

(iv) **Management dashboard**

The dashboard will be a web application written in React. It will receive live events from the backend over WebSockets and display reports using a charting library such as Chart.js.

The dashboard will also provide a visitor registration form for the guard at the registration lane. It will capture the driver's name, national ID number, vehicle registration number and purpose of visit, together with the temporary tag scanned at the desk reader. A list of temporary tags still out will show which visitors are on site.

The dashboard's main view will be a live parking map. It will show the three zones on a white background, with every numbered lot drawn as a box and coloured by its state:

- **Green: open.** The lot is free and can be assigned.
- **Red: occupied or reserved.** A vehicle is parked there, or the lot has been assigned to a vehicle that has just passed the gate.
- **Grey: inactive.** The lot is closed or its sensor is offline, so it is not assigned.

Each zone will also show how many lots are free, and the zone header will turn red when the zone is full.

&#91;embedded content: Figure 3: Dashboard parking map · 3 zones, 12 lots\]

A reserved lot is red like an occupied one, but with a dashed border, so staff can tell a vehicle on its way from one already parked.

### 3.3 Project Schedule

The schedule assumes a project completion deadline in early April 2027. It runs from 26th October 2026 to 2nd April 2027, with a break between 19th December 2026 and 4th January 2027.

&#91;embedded content: Figure 4: Gantt chart · 9 tasks, 26 Oct 2026 to 2 Apr 2027\]

The access engine is the longest task at about four weeks, because it carries the core decision logic that every later cycle depends on.

### 3.4 Budget

Table 1 shows a budget for the proposed system. Prices are approximate estimates and should be confirmed with local suppliers before submission.

| # | Item | Specification | Quantity | Unit Price (Kshs) | Amount (Kshs) |
| --- | --- | --- | --- | --- | --- |
| 1 | Development computer | Student's own laptop | 1 | 0 | 0 |
| 2 | Microcontrollers | ESP32 development board (gate and parking node) | 2 | 1,200 | 2,400 |
| 3 | HF RFID readers | RC522 13.56 MHz module (express lane and registration desk) | 2 | 800 | 1,600 |
| 4 | Secure RFID cards | DESFire EV2 or NTAG 424 DNA, including temporary tags | 5 | 300 | 1,500 |
| 5 | UHF reader module (optional) | Short-range UHF module with tags | 1 | 15,000 | 15,000 |
| 6 | Servo motors | SG90, one barrier per lane | 2 | 400 | 800 |
| 7 | Vehicle sensor at gate | HC-SR04 ultrasonic sensor | 1 | 300 | 300 |
| 8 | Lot occupancy sensors | IR obstacle sensor module | 12 | 150 | 1,800 |
| 9 | Display | 0.96" OLED | 1 | 600 | 600 |
| 10 | Components | LEDs, buzzer, breadboards, jumpers, resistors | 1 set | 1,500 | 1,500 |
| 11 | Power supply | 5 V adapter | 2 | 800 | 1,600 |
| 12 | Scale model | Acrylic sheet, model vehicles, lot markings | 1 set | 2,000 | 2,000 |
| 13 | Deployment server | Cloud VPS, 2 GB RAM | 6 months | 1,000 | 6,000 |
| 14 | Internet data | Mobile data bundles | 6 months | 500 | 3,000 |
| 15 | Printing | Draft and final copies | 1 | 1,000 | 1,000 |
| 16 | Binding | N/A | 5 | 100 | 500 |
|  | **Total** |  |  |  | **39,600** |

Table 1: Budget. Without the optional UHF module, the total is Kshs 24,600.

## References

Bertino, E., Bonatti, P. A. and Ferrari, E. (2001) TRBAC: A Temporal Role-Based Access Control Model. *ACM Transactions on Information and System Security*, 4(3), pp. 191–233. Available at: <https://www.cerias.purdue.edu/apps/reports_and_papers/view/3971> \[Accessed: 16 Oct. 2026\].

Chazanga, F. C., Phiri, J. and Namukolo, S. (2019) Development of a Two Factor Authentication for Vehicle Parking Space Control based on Automatic Number Plate Recognition and Radio Frequency Identification. *International Journal of Advanced Computer Science and Applications*, 10(1), pp. 588–597. Available at: <https://thesai.org/Downloads/Volume10No1/Paper_74-Development_of_a_Two_Factor_Authentication.pdf> \[Accessed: 16 Oct. 2026\].

Cugola, G. and Margara, A. (2012) Processing Flows of Information: From Data Stream to Complex Event Processing. *ACM Computing Surveys*, 44(3), Article 15. Available at: <https://ix.cs.uoregon.edu/~jsventek/papers/01Cugola2012.pdf> \[Accessed: 16 Oct. 2026\].

de Koning Gans, G., Hoepman, J.-H. and Garcia, F. D. (2008) A Practical Attack on the MIFARE Classic. *Smart Card Research and Advanced Applications (CARDIS 2008)*, Lecture Notes in Computer Science 5189. Springer. Available at: <https://arxiv.org/abs/0803.2285v2> \[Accessed: 16 Oct. 2026\].

European Patent Office (2010) *EP 2230624 A1: Access control system for persons and vehicles based on radio frequency identification (RFID)*. Available at: <https://data.epo.org/gpi/EP2230624A1> \[Accessed: 16 Oct. 2026\].

Fahim, A., Hasan, M. and Chowdhury, M. A. (2021) Smart parking systems: comprehensive review based on various aspects. *Heliyon*, 7(5), e07050. Available at: <https://pmc.ncbi.nlm.nih.gov/articles/PMC8141779/> \[Accessed: 16 Oct. 2026\].

Garcia, F. D., de Koning Gans, G., Muijrers, R., van Rossum, P., Verdult, R., Wichers Schreur, R. and Jacobs, B. (2008) Dismantling MIFARE Classic. *Computer Security – ESORICS 2008*, Lecture Notes in Computer Science 5283, pp. 97–114. Springer. Available at: <https://sos.cs.ru.nl/applications/rfid/2008-esorics.pdf> \[Accessed: 16 Oct. 2026\].

Juels, A. (2006) RFID Security and Privacy: A Research Survey. *IEEE Journal on Selected Areas in Communications*, 24(2), pp. 381–394. Available at: <https://www.acsu.buffalo.edu/~mblanton/cse708/rfid-survey.pdf> \[Accessed: 16 Oct. 2026\].

Kenya (2019) *The Data Protection Act, No. 24 of 2019*. Nairobi: Government Printer.

Lin, T., Rivano, H. and Le Mouël, F. (2017) A Survey of Smart Parking Solutions. *IEEE Transactions on Intelligent Transportation Systems*, 18(12), pp. 3229–3253. Available at: <https://ieeexplore.ieee.org/document/7895130> \[Accessed: 16 Oct. 2026\].

Masri, N. N. and Ab. Aziz, R. (2025) RFID-Based Vehicle Access and Monitoring System. *Applied Information Technology and Computer Science*. Universiti Tun Hussein Onn Malaysia. Available at: <https://penerbit.uthm.edu.my/periodicals/index.php/aitcs/article/view/20260> \[Accessed: 16 Oct. 2026\].

Mohandes, M., Deriche, M., Ahmadi, H., Kousa, M. and Balghonaim, A. (2016) An Intelligent System for Vehicle Access Control using RFID and ALPR Technologies. *Arabian Journal for Science and Engineering*, 41(9). Available at: <https://pure.kfupm.edu.sa/en/publications/an-intelligent-system-for-vehicle-access-control-using-rfid-and-a/> \[Accessed: 16 Oct. 2026\].

Pressman, R. (2010) *Software Engineering: A Practitioner's Approach*. New York, NY: McGraw Hill.

Sandhu, R. S., Coyne, E. J., Feinstein, H. L. and Youman, C. E. (1996) Role-Based Access Control Models. *IEEE Computer*, 29(2), pp. 38–47.

Silva, D., Carvalho, L. I., Soares, J. and Sofia, R. C. (2021) A Performance Analysis of Internet of Things Networking Protocols: Evaluating MQTT, CoAP, OPC UA. *Applied Sciences*, 11(11), 4879. Available at: <https://doi.org/10.3390/app11114879> \[Accessed: 16 Oct. 2026\].

Wang, F., Liu, S., Liu, P. and Bai, Y. (2006) Bridging Physical and Virtual Worlds: Complex Event Processing for RFID Data Streams. *Advances in Database Technology – EDBT 2006*, Lecture Notes in Computer Science 3896. Springer. Available at: <https://unpaywall.org/10.1007%2F11687238_36> \[Accessed: 16 Oct. 2026\].

Want, R. (2006) An Introduction to RFID Technology. *IEEE Pervasive Computing*, 5(1), pp. 25–33. Available at: <https://ieeexplore.ieee.org/document/1593568> \[Accessed: 16 Oct. 2026\].

Wu, E., Diao, Y. and Rizvi, S. (2006) High-Performance Complex Event Processing over Streams. *Proceedings of the 2006 ACM SIGMOD International Conference on Management of Data*. Available at: <https://www.lix.polytechnique.fr/Labo/Yanlei.Diao/publications/sase-sigmod2006.pdf> \[Accessed: 16 Oct. 2026\].