---
candidate_id: nist-ir-8501
title: Semiconductors and Microelectronics Standards
domains:
- chip_design_eda_ip
- materials_equipment
- wafer_fabrication
- packaging_testing
source_name: National Institute of Standards and Technology
source_url: https://doi.org/10.6028/NIST.IR.8501
document_type: government_report
published_at: '2023-01-01'
document_version: NIST.IR.8501
authority_level: official
claim_type: government_report
doi: 10.6028/NIST.IR.8501
license_name: NIST Technical Series public-use terms
license_url: https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications
retrieved_at: '2026-07-15T09:34:01+00:00'
content_hash: 77d0ffb7a13628d2c7f10628021f8c2e68dc72caa246c6ef22372a82bfb87b74
is_synthetic: false
---

# Semiconductors and Microelectronics Standards

NIST Interagency Report Semiconductors and Microelectronics Standards Report of the Semiconductors and Microelectronics Working Group Jason Kahn Chris Greer This publication is available free of charge from: https://doi.org/10.6028/NIST.IR.8501

NIST Interagency Report Semiconductors and Microelectronics Standards Report of the Semiconductors and Microelectronics Working Group Jason Kahn CHIPS R&D Program Office Chris Greer CHIPS R&D Program Office This publication is available free of charge from: https://doi.org/10.6028/NIST.IR.8501 December 2023 U.S. Department of Commerce Gina M. Raimondo, Secretary National Institute of Standards and Technology Laurie E. Locascio, NIST Director and Under Secretary of Commerce for Standards and Technology

Certain commercial entities, equipment, or materials may be identified in this document in order to describe an experimental procedure or concept adequately. Such identification is not intended to imply recommendation or endorsement by the National Institute of Standards and Technology, nor is it intended to imply that the entities, materials, or equipment are necessarily the best available for the purpose. NIST Technical Series Policies Copyright, Use, and Licensing Statements NIST Technical Series Publication Identifier Syntax Publication History Approved by the NIST Editorial Review Board on 2023-12-04 How to Cite this NIST Technical Series Publication Kahn J, Greer C (2023) Semiconductors and Microelectronics Standards, Report of the Semiconductors and Microelectronics Working Group. (National Institute of Standards and Technology, Gaithersburg, MD), NIST Interagency Report (IR) NIST IR 8501. https://doi.org/10.6028/NIST.IR.8501 NIST Author ORCID iDs Jason Kahn: 0000-0003-3798-8668 Christopher Greer: 0000-0002-6669-3941 Contact Information jason.kahn@nist.gov

i Abstract This report of the Semiconductors and Microelectronics Working Group of the Interagency Committee on Standards Policy (ICSP) provides an overview of Federal government semiconductors and microelectronics standards activities and recommends standards focus areas and priorities for ICSP consideration. The Recommendations to the ICSP for Strategic Standards Priority Areas section of the report lists the current Standards Developing Organizations in which the Federal government participates that are related to semiconductors and microelectronics, identifies five focus areas and priorities, and identifies gaps and opportunities for possible impacts in the future. The landscape review section provides an overview of each contributing agency’s relevant semiconductors and microelectronics standards activities, including its mission, semiconductors and microelectronics goals, participation in standards developing organizations, semiconductors and microelectronics focus areas and priorities, and semiconductors and microelectronics gaps and opportunities. The National Standards Strategy for Critical and Emerging Technology Strategy shows how the Semiconductors and Microelectronics Working Group aligns with the National Standards Strategy for Critical and Emerging Technology. Keywords semiconductors; microelectronics; interagency; international technical standards; Federal agency standards activities; standards; standards developing organizations, SDOs, standards priority areas.

ii Table of Contents Abstract........................................................................................................................................... i Keywords........................................................................................................................................ i Executive Summary...................................................................................................................... v 3.2.1.2. Defense Logistics Agency (DLA) Semiconductor and Microelectronics 3.2.1.3. Defense Logistics Agency (DLA) Participation in Standards Developing 3.2.1.4. Defense Logistics Agency (DLA) Semiconductor and Microelectronics focus 3.2.1.5. Defense Logistics Agency (DLA) Semiconductor and Microelectronics gaps and 3.2.2.2. Department of Homeland Security (DHS) Semiconductor and Microelectronics 3.2.2.3. Department of Homeland Security (DHS) Participation in Standards Developing

iii 3.2.2.4. Department of Homeland Security (DHS) Semiconductor and Microelectronics 3.2.2.5. Department of Homeland Security (DHS) Semiconductor and Microelectronics 3.2.3.3. NIST Participation in Standards Developing Organizations (SDOs) that are 3.2.4.3. US Air Force Participation in Standards Developing Organizations (SDOs) that 3.2.4.4. US Air Force Semiconductor and Microelectronics focus areas and priorities.. 24 3.2.5.2. United States General Services Administration (GSA) Semiconductor and 3.2.5.3. United States General Services Administration (GSA) Participation in Standards 3.2.5.4. United States General Services Administration (GSA) Semiconductor and 3.2.5.5. United States General Services Administration (GSA) Semiconductor and 3.2.6.2. United States Navy (USN) Semiconductor and Microelectronics Standards 3.2.6.3. United States Navy (USN) Participation in Standards Developing Organizations 3.2.6.4. United States Navy (USN) Semiconductor and Microelectronics focus areas and priorities 28 3.2.6.5. United States Navy (USN) Semiconductor and Microelectronics gaps and

## NIST IR 8501

December 2023 iv

v Executive Summary This report of the Semiconductors and Microelectronics Standards Working Group (SMSWG or Working Group) of the Interagency Committee on Standards Policy (ICSP) provides an overview of Federal government semiconductors and microelectronics (SMS) voluntary consensus standards activities and outlines standards focus areas and priorities for ICSP consideration. Additionally, this report defines gaps and opportunities where the Federal government could potentially make an impact in the future. The primary strategy for Federal agency engagement in standards development, as set out in Circular A-119 from the Office of Management and Budget (OMB) and the National Technology Transfer and Advancement Act (NTTAA), focuses on reliance on private sector leadership supplemented by Federal government contributions to discrete standardization processes. Participation by agencies in standards activities focuses on open, consensus-based, voluntary, private sector-led, and science- and engineering-informed standards that enable:

- Innovation in products and services;

- Interoperability across systems and devices;

- Open and competitive national and global markets; and

- Efficient and effective acquisition processes. The SMSWG was chartered by the ICSP to enable interagency coordination on semiconductors and microelectronics standards efforts. Nine Federal agencies, departments, and offices are participating in this interagency group. This annual report of the Working Group to the ICSP provides current SMS activities of participating Federal agencies and recommendations for strategic directions in relevant Federal standards efforts. This is done by outlining:

- The current Standards Developing Organizations (SDOs) that in which the Federal government participates

- The current focus areas and priorities within SMS

- The identified gaps and opportunities for future influence in SMS. The SMS focus areas and priorities section of the report sets out five areas for consideration by the ICSP.

- Supply Chain and Security – The measures taken to ensure the integrity and reliability of semiconductor components throughout their production and distribution process.

- Chiplets – An integrated circuit that contains a subset of functionality and can be combined with other chiplets in a single package to create a larger, more powerful chip, which provides several advantages over a traditional system on chip such as reusable IP and reduced cost via heterogeneous integration.

- Performance – The operational characteristics of a device or system, such as speed, power consumption, and reliability. It can also refer to the ability of a device to process data, perform computations, and execute tasks efficiently and effectively.

vi

- Metrology and Measurement Science – The science of measurement and the development of measurement standards for the semiconductor and microelectronics industry.

- Digital Twin – A virtual representation of a physical object or system that is created with collected data and updated with real-time data. A digital twin needs data about an object or process to create a virtual model that can mimic the behaviors or states of the real-world item or procedure. This data may cover the entire lifecycle of a product and include design specifications, production processes, or engineering information. Digital twins can help accelerate the chip design and manufacturing process, improve performance without affecting full-capacity operations, and enable solutions such as predictive maintenance and optimized scheduling and dispatch. To provide an overview of contributing relevant SMS standards activities, the landscape review section provides, for each contributing Federal agency or unit that chose to submit information, a description of the following.

- Agency Mission

- Semiconductor and Microelectronics Standards (SMS) Goals

- Standards Developing Organizations (SDOs) that are related to SMS

- Semiconductor and Microelectronics focus areas and priorities

- Semiconductor and Microelectronics gaps and opportunities

1 Introduction and Overview Strategy and Policy for Government Engagement in Standards Development As described below, it is the policy of the Federal government to rely on the private sector led voluntary consensus standards whenever possible. Voluntary consensus standards development processes are those that are open, balanced, and consensus-based, with provisions for due process and appeals. Voluntary consensus standards that are informed by good science and engineering can be a powerful force for:

- Innovation in products and services development;

- Interoperability across systems and devices;

- Open and competitive national and global markets; and

- Efficient and effective acquisition processes. Reliance on private sector leadership, supplemented by Federal government participation and contributions during the development of standards, remains the primary U.S. strategy for government engagement in standards development. This strategy is implemented in both legislation and policy. With respect to legislation, the National Technology Transfer and Advancement Act (P.L. 104-113 or NTTAA) directs Federal agencies to use technical standards “that are developed or adopted by voluntary consensus standards bodies, using such technical standards as a means to carry out policy objectives or activities determined by the agencies and departments.” The Act further provides that “Federal agencies and departments shall consult with voluntary, private sector, consensus standards bodies and shall, when such participation is in the public interest and is compatible with agency and departmental missions, authorities, priorities, and budget resources, participate with such bodies in the development of technical standards.” The National Institute of Standards and Technology (NIST) is charged with coordinating Federal agency implementation of NTTAA provisions. The Trade Agreements Act of 1979 (as amended) prohibits U.S. agencies from engaging in standards-related activities that create unnecessary obstacles to trade and gives the U.S. Trade Representative (USTR) the responsibility to coordinate the consideration of international trade policy issues related to standards and conformity-assessment procedures. With respect to policy, a central element in implementing the National strategy is Office of Management and Budget (OMB) Circular A-119 on Federal Participation in the Development and Use of Voluntary Consensus Standards and in Conformity-Assessment Activities. The Circular directs agencies to use voluntary consensus standards in lieu of government-unique standards except where inconsistent with law or otherwise impractical. It also provides guidance to agencies on participation in the development of voluntary consensus standards and articulates policies relating to the use of standards by Federal agencies.

2 The October 2011 memorandum1 from the Subcommittee on Standards of the National Science and Technology Council provides a high-level overview of the legal and policy framework for government engagement in private-sector standards and sets out the following fundamental objectives for Federal government engagement in standards activities.

- Ensure timely availability of effective standards and efficient conformity assessment schemes critical to addressing national priorities

- Achieve cost-efficient, timely, and effective solutions to regulatory, procurement, and policy objectives

- Promote standards and standardization systems that enable innovation and foster competition

- Enhance U.S. competitiveness while ensuring national treatment

- Facilitate international trade and avoid the creation of unnecessary obstacles to trade Interagency Committee on Standards Policy This technical report provides an analysis of the semiconductors and microelectronics standards landscape based on input from the participating Federal agencies. The Interagency Committee on Standards Policy (herein after referred to as the “ICSP” or “Committee”) advises federal agencies on matters related to standards policy, as required under the National Technology Transfer and Advancement Act of 1995 (NTTAA). The ICSP provides a forum for coordination on policies related to Federal participation and use of standards and conformity assessment consistent with OMB Circular A-119. It reports to the Secretary of Commerce through the Director of the National Institute of Standards and Technology (NIST) and the Director of NIST’s Standards Coordination Office (SCO). The Committee's authority is set out in Section 13 b of OMB Circular A-119 Federal Participation in the Development and Use of Voluntary Consensus Standards and in Conformity Assessment Activities of the Office of Management and Budget (OMB). The Circular establishes policy to be followed by executive agencies in participating in activities of voluntary standards organizations and in adopting and using voluntary standards. The Circular was last revised on February 10, 1998 and was published in the Federal Register (63 FR 8545) on February 19, 1998. The purpose of the Committee is to promote effective participation by the Federal Government in domestic and international standards and conformity assessment activities and the adherence to uniform policies by Federal agencies in the development and use of standards and in conformity assessment activities. Well-considered Federal policies reflecting the public interest can expedite the development and adoption of standards that stimulate competition, promote innovation, and protect the public safety and welfare. The objective of the Committee is to promote effective and consistent standards and conformity assessment policies in furtherance of https://www.nist.gov/system/files/documents/standardsgov/Federal_Engagement_in_Standards_Activities_October12_final.pdf

3 U.S. goals and to foster cooperative participation by the Federal Government, U.S. industry, and other private organizations in standards and conformity assessment activities. More information is available at: https://www.nist.gov/standardsgov/interagency-committee-standards-policy-icsp . Semiconductors and Microelectronics Standards Working Group The Semiconductors and Microelectronics Standards Working Group (herein after referred to as the “SMSWG” or “Working Group”) is established under the provisions of the charter of the Interagency Committee on Standards Policy (ICSP). The objective of the SMSWG is to facilitate coordination of Federal agency semiconductors and microelectronics standards (SMS) activities, respond to requests for information, and develop recommendations relating to SMS standards policy matters to the ICSP. The SMSWG is responsible for:

1. Assisting the ICSP in promoting effective and consistent federal policies in the area of semiconductor and microelectronics standards.

2. Providing an annual report to the ICSP on the current SMS activities of participating Federal agencies and recommendations for strategic directions in relevant Federal standards efforts.

3. Responding to requests for information and advising the ICSP on effective means of coordinating SMS activities with those of the private sector.

4. Sharing best practices in semiconductor and microelectronics standards among Federal agencies.

5. Coordinating Federal semiconductor and microelectronics standards interests across application areas such as transportation, energy, health, public safety, and others. This report was developed under the provisions of item (2) above. Definition of Semiconductors and Microelectronics Semiconductors and microelectronics, in terms of the scope of this document, include the entire lifecycle of integrated circuits, chips, system-on-chips, and other related facets. It also includes supply chain aspects, manufacturing. computing, memory, and storage technologies, which affect every corner of the global economy, society, and government, and which power a panoply of innovations and capabilities. [1][2]

4 Recommendations to the ICSP for Strategic Standards Priority Areas The SMSWG charter directs the Working Group to provide an annual report to the ICSP, including “recommendations for strategic directions in relevant Federal standards efforts.” Through its regular meeting process, the Working Group identified Participation in Standards Developing Organizations (SDOs), Current Focus Areas and Priorities, and Gaps and Opportunities. Participation in Standards Developing Organizations (SDOs) The following is a list of the external Standards Developing Organizations (SDOs) in which the Federal government is currently participating that are related to SMS. Participation can be observation of the outputs of an SDO, attendance of meetings and calls, contribution to documentary standards from SDOs, and leadership within an SDO. Although this list is accurate, it is not necessarily an exhaustive list:

- JEDEC (Joint Electronic Engineering Device Engineering Council) [1] Examples: o JEDEC JC-13 Committee is responsible for standardizing quality and reliability methodologies for solid state products used in military, space, and environments requiring special use condition capabilities beyond those of standard commercial practices.  JC- 13.1 (Semiconductors)  JC -13.2 (Monolithic Microcircuits)  JC -13.4 (Radiation Hardness Assurance)  JC -13.5 (Hybrid Microcircuits)  JC- 13.7 (New Technologies)

- Society of Automotive Engineers (SAE) [2] Examples: o CE-11 (Passive Components) o CE-12 - Solid State Devices

- IPC (Formerly Institute of Printed Circuits) [3] Examples: o Pb-Free Electronics Risk Management (PERM) Council o 7-11 - Test Methods o B-10 Packaged Electronic Components Committee o B-10a Plastic Chip Carrier Cracking Task Group o D-21B IPC-2252 Task Group o D-21C High Speed/high Frequency Controlled Impedance o D-21 - High Speed/high Frequency Design o D-24 - High Speed/high Frequency Test Methods o 2-15 - Supply Chain Communication Subcommittee o 2-15A Product Data Exchange Task Group o 2-15C Product Genealogy Exchange Task Group o 2-15D Product Manufacturing Quality Exchange Task Group o 2-15 EProduct Design Configuration Exchange Task Group

5 o 2-19b Trusted Supplier Task Group o D-33-ap Ultra HDI Subcommittee o D-54 - Embedded Devices Test Methods o D-50 - Embedded Components Committee o D-70 - E-Textiles Committee o D-74a - Printed Electronics E-Textiles Electrical Test Task Group o D-74 - E-Textile Test Methods Development and Validation Subcommittee

- IEEE (Institute of Electrical and Electronics Engineers) [4] Examples: o C006 - Board Of Governors o WG299 – Electromagnetic Shielding Enclosures o C63 - Electromagnetic Compatibility o TC-10 - Waveform Generation, Measurement And Analysis o N42.38 - Performance Criteria For Spectroscopy Based Portal Monitors Used For Homeland Security o N42.49 - Performance Criteria For Personal Emergency Radiation Detectors (perds) For Exposure Control o MEMS – Microelectronmechanical Systems Standards Sponsor Committee o C63.27 - Evaluation Of Wireless Coexistence o APS/SC - Antennas and Propagation Standards Committee o IEEE P1900.8 - Machine Learning For Rf Spectrum Awareness In Dynamic Spectrum Access (DSA) And Sharing Systems (COM/DYSPAN-SC/MLSA)

## (IEEE P1900.8)

o TC9.P1451.5.10 - Standard for a Smart Transducer Interface for Sensors and Actuator -- Wireless Communication Protocols and Transducer Electronic Data Sheet (TEDS) NB-IoT Protocol Working Group (NB-IoT Protocol WG)

- EOS/ESD Association (ESDA) [5]

- ASTM International (formerly known as American Society for Testing and Materials) [6] Example: o Committee F42 on Additive Manufacturing Technologies

- ISO and ISO/IEC [7] [8] Examples: o (ISO/IEC) JTC 1/SC 37 - Biometrics o (ISO) TC 213/WG 6 - General Requirements For Geometrical Product Specification (GPS) Measuring Equipment o (ISO) TC 201/SC 6 - Secondary Ion Mass Spectrometry o (ISO) TC 213/WG 16 - Areal and Profile Surface Texture o (ISO) TC 213 - Dimensional and Geometrical Product Specifications and Verification o (ISO) ISO/TC 201/SC 10 - X-ray Reflectometry (XRR) and X-ray Fluorescence (XRF) Analysis

- IEC [9] Examples: o TC 29/WG 5 - Working Group: Measurement Microphones o TC 47 Semiconductor devices o TC 65 Industrial-process measurement, control and automation

6 o TC 73 Short-circuit currents

- Semiconductor Equipment and Materials International (SEMI) [10] Examples: o Wafer Bond o MEMS Reliability WG o C009 North America Region Standards Committee o Inspection And Metrology Task Force o C012 Gases o C007 Liquid Chemicals o Photovoltaic o C001 Silicon Wafer o Bonded Wafer Stack Task Force o Technical Architect Board o Traceability Committee o 3DS-IC Three Dimensional Stacked Integrated Circuits o C010 Microlithography o SC.01 Materials Characterization o SC.01 Patterning Committee o TF.01 Advanced Surface Inspection o C018 Compound Semiconductor Materials o TF.02 Line Edge Roughness o C033Anti-counterfeiting Workgroup o MEMS/NEMS Micro-electro-mechanical Systems/nano-electro-mechanical Systems o TF.05 Overlay Metrology Specifications

- International Technology Roadmap for Semiconductors (ITRS) [11] Examples: o Metrology Technical Working Group o Emerging Research Materials

- ANSI [12] Current Focus Areas and Priorities The following is a list of the current topics, focus areas, and priorities related to semiconductors and microelectronics that the Federal government finds important: 2.2.1. Supply Chain and Security The measures taken to ensure the integrity and reliability of semiconductor components throughout their production and distribution process. [13] [14][15]

- Secure Processors – A secure processor is a processor that has added encryption and key management to protect data and software from unauthorized access. It may also be a coprocessor that is designed and hardened against side-channel attacks and physical tampering. A

7 secure processor can run software programs in a trusted execution environment. [16] [17]

- Authenticity and counterfeit – Counterfeit semiconductor components are electronic parts whose origin or quality is deliberately misrepresented. Counterfeiting of electronic components can infringe the legitimate producer's trademark rights. Because counterfeit parts often have inferior specifications and/or quality, they may represent a hazard if incorporated into critical systems. [19][20][21][22]

- Availability and scarcity – The global demand for semiconductors is growing rapidly, due to the increasing use of electronics. However, the supply of semiconductors is currently not keeping pace with demand due to several factors. [23][24]

- GEM (Generalized Emulation of Microcircuits) and AME (Advanced Microcircuit Emulation) – Technologies and programs that provide a continuing solution to the microelectronics diminishing manufacturing sources problem. The GEM program is responsible for production manufacturing and the AME program performs development and integration in support of future technology needs. The Programs deliver a permanent solution to microcircuit obsolescence that can be utilized during any phase of the weapon system life cycle. [25][26] 2.2.2. Chiplets A chiplet is an integrated circuit that contains a subset of functionality and can be combined with other chiplets in a single package to create a larger, more powerful chip, which provides several advantages over a traditional system on chip such as reusable IP and reduced cost via heterogeneous integration. [27]

- Interconnects – The connections between several specialized, smaller semiconductor devices within a package to create a system-in-package (SiP). [28][29]

- Packaging – Generally, packaging is the encapsulation of an integrated circuit in a specially designed housing. For chiplets, it is a method of creating complex integrated circuits by combining modular chips, each with specialized functionality. [30][31][32]

- Interoperability – The ability of chiplets from different providers to work together seamlessly within a system. The goal is to create a system comprised of chiplets that can function together as a single unit, regardless of the source of the individual chiplets. [33]

8 2.2.3. Performance The operational characteristics of a device or system, such as speed, power consumption, and reliability. It can also refer to the ability of a device to process data, perform computations, and execute tasks efficiently and effectively. [34][35][36][37] Examples of performance specification from internal Federal sources:

- specification MIL-PRF-19500

- specification MIL-PRF-38534

- specification MIL-PRF-38535 2.2.4. Metrology and Measurement Science The science of measurement and the development of measurement standards for the semiconductor and microelectronics industry. [38]

- Materials Purity and Properties – New metrology is needed to meet increasingly stringent requirements for semiconductor material purity, physical properties, and provenance. This involves the journey of a material from production to end use. [39]

- Future Microelectronics Manufacturing – Future microelectronics manufacturing involves the development of new measurement methods, data, reference artifacts, models, and theory to enable higher device yields and reliability, lower costs, improved fabrication, and performance¹. Advances in measurement science, standards, materials, instrumentation, testing, and manufacturing capabilities will be needed to help design, develop and manufacture next-generation microelectronics. [38]

- Advanced Packaging – Advanced packaging refers to the integration of separately manufactured components. Advanced packaging is a key area of focus in chiplet technology. It allows for the assembly of various types of third-party chips such as I/Os, memory, and processor cores in a package. [40] 2.2.5. Digital Twin A digital twin is a virtual representation of a physical object or system that is created with collected data and updated with real-time data. A digital twin needs data about an object or process to create a virtual model that can mimic the behaviors or states of the real-world item or procedure. This data may cover the entire lifecycle of a product and include design specifications, production processes, or engineering information. Digital twins can help accelerate the chip design and manufacturing process, improve performance without affecting full-capacity operations, and enable solutions such as predictive maintenance and optimized scheduling and dispatch. [41][42][43]

- Manufacturing process and equipment management –

9 Manufacturing process and equipment management is the use of a virtual model of a physical manufacturing process to analyze the production performance. It uses real-time data from sensors and other source. [47]

- Quality control – Quality control is the use of a virtual model of a real-world product or service to ensure that it meets the expected requirements. It uses real-time data from sensors and other sources to create a dynamic replica of the physical product or service. It is used to prevent and detect defects, reduce waste, and improve customer satisfaction. [48]

- Supply chain management and assurance – Supply chain management and assurance is the use of a virtual model of a the real-world supply chain and its processes. It uses real-time data from sensors and other sources to create a dynamic replica of the physical supply chain and its components. It can help improve supply chain visibility, traceability, security, and sustainability. [49] [50] Gaps and Opportunities In addition to the current strategic priority areas, there were areas identified as gaps or opportunities. These areas where there could be Federal government involvement but there is currently little or none; or Semiconductor and Microelectronics areas that are trending and there are currently gaps in Federal government involvement:

- Chiplets open standards and de facto standards organizations The leading organizations that are standardizing chiplets usage and interoperability are trending towards being private enterprises. Organizations, such as the UCIe, bunch of wires (BoW), OpenHBI, and OIF XSR, are made up of private companies and entities and usually government involvement is not allowed. The Federal government could pursue membership opportunities in these organizations to assist in the forward movement of chiplets standardization.

- Diminishing Manufacturing Sources and Material Shortages (DMSMS) [44] – A DMSMS issue is the loss, or impending loss, of manufacturers, suppliers, or raw materials. Because many manufacturing facilities or material sources exist internationally and in sometimes hostile arenas, there is a potential for greater instability. The Department of Defense (DoD) has published two guidebooks, SD-22 [45] and SD-26 [46], to help manage DMSMS and parts management. Even though there are multiple standards that address DMSMS, in order to mitigate issues that result in obsolescence, loss of manufacturing sources, or material shortages, more or additional international standards that assess the potential of negative impacts and the resulting mitigation strategies may be needed.

- Government-Industry Data Exchange Program (GIDEP) [18] – GIDEP is a cooperative activity between government and industry participants seeking to reduce or eliminate expenditures of resources by sharing technical information essential during research, design, development, production, and operational phases of the life cycle of systems, facilities and equipment. Since GIDEP's inception, participants have reported over $2.1 billion in prevention of unplanned expenditures. That means without GIDEP,

10 participants could have potentially realized additional expenses of over $2.1 billion. Proper utilization of GIDEP data can materially improve the total quality and reliability of systems and components during the acquisition and logistics phases of the life cycle and reduce costs in the development and manufacture of complex systems and equipment. Moving the GIDEP activities into an internationally recognized and standardized process could increase adoption of the concept.

- Third-party IP verification and validation for application specific integrated circuit (ASIC) and field-programmable gate array (FPGA) design – In order to reduce costs and decrease the design time cycle, third-party intellectual property is sometimes used. To ensure that the affected ASICs, FPGAs, and other similar products correctly function and satisfy specific requirements, verification and validation is needed. This can also ensure that third-part IP is not performing functions in addition to the intended purpose. Standardized validation and verification could be done in accredited laboratories.

- Microelectronic Lifecycle Models – These are comprehensive digital models rooted in the physical implementation model of the microelectronics, extending through the board, system, and mission digital models. A true digital twin model of the system, developed from the bottom up based on the implemented microelectronics, enables a top-down requirements push to accelerate microelectronics technology refresh, minimize lifetime buys, predict and resolve obsolescence, and accelerate certification. A possible gap in standards development for Microelectronic Lifecycle Models is the need for a defined common framework which takes into account the different needs of the stakeholders.

- Secure Processors – Developing standards for secure processors has been challenging because of the wide range of stakeholders and specialized needs that prevent generalized requirements for being valid in most situations. There is a need for more collaboration and coordination among the various parties involved in the microelectronics supply chain.

- Certification – Microelectronics for DoD applications require adherence to higher standards than general commercial microelectronics. The certification process varies depending on the certifying organization and the specific certification being pursued. Common artifacts, tests, and processes used for certification could be leveraged between different certification efforts to reduce cost and schedule. Continuous testing and integration during microelectronics development can rapidly accelerate certification by delivering and verifying certification artifacts during development and post-fabrication.

- Obsolescence – Due to the rapid evolution of microelectronics, volatility within the vendor marketplace, and lead time to fielding for systems utilizing microelectronics, there is a risk that many of the microelectronic components may be obsolete or no longer supported by the time the system is fielded. Designing for upgrade, utilizing digital engineering within the microelectronics, allows for a bottom-up true digital model to rapidly simulate and develop technology refresh options reducing the risk of obsolescence.

11 Contributing Agency/Office SMS Standards Landscape Overview Agencies/Offices Participating in the Semiconductors and Microelectronics Standards Working Group

- Department of Defense (DoD)

- Defense Logistics Agency (DLA)

- Department of Homeland Security (DHS)

- National Institute of Standards and Technology (NIST)

- US Air Force

- US Army

- US General Services Administration (GSA)

- US Navy

- US Space Force (USSF) Contributing Agency Standards Landscape Overview current SMS activities of participating Federal agencies and recommendations for strategic directions in relevant Federal standards efforts." This section provides an overview for each contributing agency or office that chose to provide such information for this report. The information provided is: the agency mission, semiconductor and microelectronics standards (SMS) goals for the agency, agency participation in standards developing organizations (SDOs) that are related to SMS, agency semiconductor and microelectronics focus areas and priorities, and semiconductor and microelectronics gaps and opportunities as identified by the agency. Participation in an SDO can be observation of the outputs of an SDO, attendance of meetings and calls, contribution to documentary standards from SDOs, and leadership within an SDO. While this section may not provide a comprehensive overview for each contributing agency, it does offer accurate insights and a glimpse into the standard activities and topics of interest pursued by the contributing agencies.

12 3.2.1. Defense Logistics Agency (DLA) 3.2.1.1. Defense Logistics Agency (DLA) Mission Deliver readiness and lethality to the Warfighter Always and support our Nation through quality, proactive global logistics. https://www.dla.mil/About-DLA/ 3.2.1.2. Defense Logistics Agency (DLA) Semiconductor and Microelectronics Standards (SMS) Goals The Defense Logistics Agency (DLA) goal is to deliver high reliable semiconductors and microcircuits devices to DLA supply chain for end user application of US military services, other federal agency i.e., NASA and allied nations. The Defense Standardization Program (DSP) is established by DoD Instruction 4120.24, in pursuant to sections 2451, 2452 and 2457 of title 10, United States Code. Under DSP programs DSPO's projects and initiatives fall within the following core program of semiconductors and microcircuits areas:

- Diminishing Manufacturing Sources and Material Shortages (DMSMS)

- Government-Industry Data Exchange Program (GIDEP)

- Qualification

- Non-Government Standards DLA Land and Maritime is responsible for DOD’s semiconductor and microcircuits qualification program. The qualification improves readiness by ensuring the availability of products with requisite quality, reliability, performance, and safety from trusted manufacturers or distributors. Qualification can also help reduce costs by eliminating repetitive surveillance audits and tests. Products or manufacturers qualified to the requirements in a governing specification, are published on a corresponding Qualified Product List (QPL) or Qualified Manufacturers' List (QML) in the Qualified Product Database (QPD) and published in the ASSIST website (https://assist.dla.mil/) and DLA Land and Maritime website (https://landandmaritimeapps.dla.mil/) for Standard microcircuits drawings (SMD) devices. DLA Land and Maritime, Documents Standardization Division manages 17,428 standardization documents of which Semiconductor devices specifications MIL-PRF-19500, Integrated Microcircuits specification MIL-PRF-38535 and Hybrid Microcircuits MIL-PRF-38534 devices support military terrestrial, avionic, space, satellite communications, and strategic defense applications over 50+ years. MIL-PRF-19500 (FSC 5961: semiconductor device) program supported by 13 qualified manufacturers, 32+ certified fabrication and assembly facilities are supplying 26,010+ transistors, diode and optocoupler devices for supporting warfighters and space mission. MIL-PRF-32535 and MIL-RF-38534 (FSC 5962: Microcircuits device) program supported by 54+ qualified manufacturers, 26+ certified fabrication and 12+ assembly facilities are supplying

13 28,752 + devices including logic, memory, microcontroller, microprocessor, ASIC FPGA and radiation hardness assurance (RHA) devices for supporting warfighters, DOD weapon systems, and space satellite mission. 3.2.1.3. Defense Logistics Agency (DLA) Participation in Standards Developing Organizations (SDOs) that are related to SMS DLA Land and Maritime has actively participated in developing specifications and standards for over 60 years, collaborating with numerous external Standards Developing Organizations (SDOs) and Non-Government Standards (NGS) bodies, such as the Joint Electronic Engineering Device Engineering Council (JEDEC).JEDEC JC-13 Committee is responsible for standardizing quality and reliability methodologies for solid state products used in military, space, and environments requiring special use condition capabilities beyond those of standard commercial practices. JC- 13.1 (Semiconductors), JC -13.2 (Monolithic Microcircuits), JC -13.4 (Radiation Hardness Assurance), JC -13.5 (Hybrid Microcircuits), JC- 13.7 (New Technologies), Society of Automotive Engineers (SAE), SAE CE-11 (Passive Components), IPC for Printed wiring boards, IEEE/NSREC for microcircuit devices effects on nuclear and space radiation environment and ESDA for ESD related program. 3.2.1.4. Defense Logistics Agency (DLA) Semiconductor and Microelectronics focus areas and priorities DLA Land and Maritime focuses semiconductor and microcircuits devices secure supply chain, traceability and mitigating counterfeit product to supply chain, resolve devices diminishing manufacturing sources and martials shortage (DMSMS) issue and adopt new technology devices standardization activities for warfighters. To keep DLA supply chain secure and deliver high reliability devices to the warfighters, DLA Land and Maritime qualification program conducted audit and certification to the QPL and QML manufacturers facilities for devises traceability and high reliable quality inspection over 50+ years.

1) One of the critical semiconductor’s devices specification MIL-PRF-19500 (FSC 5961: semiconductor device) program supported by 13 qualified manufacturers, 32+ certified fabrications and assembly facilities and are supplying 26,010+ transistors, diode and optocoupler types of devices for supporting warfighters and successful space mission. DLA Land and Maritime working with manufacturers and users’ communities to explore new technology Gallium Nitride (GaN) and Silicon Carbide (SiC) semiconductor devices beside traditional Silicon technology devices wherein GaN and SiC devices are faster and more efficient than silicon technology devices for using in harsh environment like higher temperature environment, low earth orbit (LEO), geosynchronous equatorial orbit (GEO), and deep-space exploratory missions. Another challenge that is a critical risk for the industry is the single/sole source supplier for semiconductor devices manufacturing process. For example, Glass diode semiconductor high voltage products such as glass tubing sleeves, produced by a single source company – Schott AG in Germany, are only supplied every 3-5 years as melting runs are infrequent due to toxicity and lead contamination concerns impacting other glass manufactured products. Also, wafer substrates and package frames are

14 made by non-domestic suppliers which are major concerns of supply chain risk or disruption by geopolitical issues.

2) DLA Land and Maritime’s most critical microcircuits device specifications MIL-PRF- 38535 and MIL-PRF-38534 (FSC 5962: Microcircuits device) programs that are supported by 54+ qualified manufacturers, 26+ certified fabrications and 12+ assembly facilities and are supplying 28,752 + devices including logic, memory, microprocessor, ASIC FPGA and radiation hardness assurance (RHA) devices for supporting warfighters, DOD weapon systems, and space satellite mission.

3) Design requirements for modern electronics and satellite/warfare systems are growing faster and moving forward with advanced complex package technologies. DLA Land and Maritime is working with microcircuits manufacturers, original equipment manufacturers (OEM) and space communities for developing new technology specification. For an example DLA is working with Advanced Technology Microcircuits (MIL-PRF-ATM) for complex multi-chip module (MCM), 2.5D, 3D types of package technology Chip on wafer on Silicon (CoWoS), chiplets type devices for next generation AI and space flight high speed computing networks systems.

4) Continue expanding the capabilities of the GEM (Generalized Emulation of Microcircuits) Program. GEM is managed by DLA and was started in 1987 as a collaborative effort between Sarnoff Corp (now SRI International) and DLA. Older microelectronics parts were no longer manufactured. But these parts were and still are used in military systems. GEM has a sister program AME, Advanced Microcircuit Emulation. AME develops the technology used by GEM, increasing the types of parts GEM is able to manufacture. Microcircuits are designed and manufactured to be a Form/Fit/Function/Interface (F3I) replacement. They are manufactured on a captive, QML (MIL-PRF-38535) certified, DoD Trusted wafer fab and manufacturing line. Transparent to supply and logistic system: same NSN, or part number and will include the GEM part number & CAGE code (0DKS7). Designed to all types of specifications. 3.2.1.5. Defense Logistics Agency (DLA) Semiconductor and Microelectronics gaps and opportunities Pursuant of Chips Act 2022, DLA Land and Maritime is working with DOD DMCFT working group, SDO’s, various Working Groups, OEM and manufacturers for developing a new technology devices specifications and standards for supporting warfighters, and improvement of future modern technology microcircuits devices for using DOD and Space mission.

1) Gallium Nitride (GaN) and Silicon Carbide (SiC) technology: DLA Land and Maritime is preparing new technology Gallium Nitride (GaN) and Silicon Carbide (SiC) semiconductor devices transistors devices specification that are faster and more efficient than silicon technology devices for using in the harsh environment like higher temperature environment, low earth orbit (LEO), geosynchronous equatorial orbit (GEO), and deep-space exploratory missions. Looking for suppliers of future technology laser diode devices.

15

2) Advanced technology microcircuits (MIL-PRF-ATM): DLA Land and Maritime is working with microcircuits manufacturers, SAE, JEDEC, original equipment manufacturers and space communities for developing new specification Advanced technology microcircuits (MIL-PRF-ATM) for complex microcircuits devices multichip module (MCM), 2.5D, 3D type of packages “Chip on Wafer on Silicon(CoWoS), Chiplets type devices for using next generation AI and Space application high speed spacecraft computing networks systems.

3) Supply Chain secure with devices DNA marking: The Defense Logistics Agency (DLA) top priority is warfighter support. As a U.S. Department of Defense (DoD) combat support agency and has firmly committed to a robust counterfeit mitigation strategy that protects our warfighters and the vital missions that they perform. DLA Land and Maritime - Electronics Product Testing center is currently marking with deoxyribonucleic acid (DNA) to an authentic DLA-managed items within the Federal Supply Class (FSC) 5962, Electronic Microcircuits.

4) Diminishing Manufacturing Sources and Material Shortages (DMSMS): A DMSMS issue is the loss, or impending loss, of manufacturers or suppliers of items or, raw materials. The DOD loses a manufacturer or supplier when that manufacturer or supplier discontinues production or support of needed items, raw materials, or software or when the supply of raw material is no longer available. DoD is highly reliant on foreign suppliers, increasingly vulnerable to disruption of supply chains, and suffering from mounting Diminishing Manufacturing Sources and Material Shortages (DMSMS) challenges. For minimizing DMSMS issue an Advanced Microcircuit Emulation (AME) program develops continuing technical capability for providing Military Specification (MIL-SPEC) form, fit and function equivalent IC’s to mitigate electronic obsolescence in new and existing weapons systems. That technical capability is transitioned to DLA Land and Maritime’s Generalized Emulation of Microcircuits (GEM) Program for implementation as a production capability for continuing support warfighter’s.

5) Government-Industry Data Exchange Program (GIDEP): GIDEP is a cooperative activity between government and industry participants seeking to reduce or eliminate expenditures of resources by sharing technical information essential during research, design, development, production, and operational phases of the life cycle of systems, facilities and equipment. Since GIDEP's inception, participants have reported over $2.1 billion in prevention of unplanned expenditures. That means without GIDEP, participants could have potentially realized additional expenses of over $2.1 billion. Proper utilization of GIDEP data can materially improve the total quality and reliability of systems and components during the acquisition and logistics phases of the life cycle and reduce costs in the development and manufacture of complex systems and equipment.

16 3.2.2. Department of Homeland Security (DHS) 3.2.2.1. Department of Homeland Security (DHS) Mission With honor and integrity, we will safeguard the American people, our homeland, and our values. https://www.dhs.gov/mission 3.2.2.2. Department of Homeland Security (DHS) Semiconductor and Microelectronics Standards (SMS) Goals No specific goals at this time. 3.2.2.3. Department of Homeland Security (DHS) Participation in Standards Developing Organizations (SDOs) that are related to SMS

1) International Electrotechnical Commission (IEC): The IEC is a global organization that publishes international standards for all electrical, electronic, and related technologies, including microelectronics.

2) Institute of Electrical and Electronics Engineers (IEEE): IEEE develops and publishes a wide range of standards for various areas of technology, including microelectronics, integrated circuits, and semiconductor devices.

3) Joint Electron Device Engineering Council (JEDEC): JEDEC is focused on developing standards for the microelectronics industry, particularly related to semiconductor devices and memory technologies.

4) Semiconductor Equipment and Materials International (SEMI): SEMI creates standards for the semiconductor and microelectronics manufacturing supply chain, covering aspects such as equipment, materials, and processes.

5) American National Standards Institute (ANSI): ANSI oversees the development of consensus-based standards across various industries, including microelectronics.

6) International Organization for Standardization (ISO): ISO publishes international standards for a wide range of industries, including those related to microelectronics and semiconductor technologies.

7) Consumer Technology Association (CTA): CTA focuses on standards development for consumer electronics, including microelectronics-based products.

8) Electronic Components Industry Association (ECIA): ECIA is involved in setting standards and best practices for the electronic components industry, which includes microelectronics.

9) Nanoelectronics Research Initiative (NRI): NRI focuses on developing standards and research in the field of nanoelectronics, which is closely related to microelectronics.

10) Global Semiconductor Alliance (GSA): GSA works on collaboration and standards in the semiconductor industry, addressing various aspects of microelectronics.

17

11) ISO/IEC Joint Technical Committee 1 (JTC 1): This committee develops standards for information technology, including microelectronics, covering topics such as data interchange formats, security, and more.

12) NIST (National Institute of Standards and Technology): NIST supports industry and the private sector in the development of standards and guidelines in various technology fields, including microelectronics, focusing on measurements, testing, and technological innovation.

13) Accredited Standards Committee (ASC) C63® - EMC: This committee focuses on standards related to electromagnetic compatibility (EMC), which is crucial in the design and operation of microelectronic devices to ensure they work without interference.

14) VITA (VMEbus International Trade Association): VITA develops standards for embedded computing systems, including those based on microelectronics, focusing on open architectures and interconnect standards.

15) Bluetooth Special Interest Group (SIG): While not exclusively focused on microelectronics, this group develops standards for short-range wireless communication technologies like Bluetooth, which are integral to many microelectronic devices.

16) USB Implementers Forum: Similar to Bluetooth SIG, this forum focuses on the development and promotion of Universal Serial Bus (USB) standards, which are widely used in microelectronics for data and power transfer.

17) PCI-SIG (Peripheral Component Interconnect Special Interest Group): This group focuses on developing and maintaining standards for the PCI Express (PCIe) interconnect technology widely used in microelectronics.

18) iPC - Association Connecting Electronics Industries: IPC develops standards for the electronics manufacturing industry, including packaging and assembly processes. They cover areas such as printed circuit boards (PCBs), surface mount technology (SMT), and electronic assembly processes.

19) IEEE CPMT (Components, Packaging, and Manufacturing Technology) Society: This IEEE society focuses on standards related to the packaging and manufacturing of electronic components. They cover topics such as interconnect technologies, thermal management, and advanced packaging methods. 3.2.2.4. Department of Homeland Security (DHS) Semiconductor and Microelectronics focus areas and priorities

1) Supply Chain Security: Ensuring the security and resilience of the semiconductor supply chain is a top priority. DHS Science and Technology Directorate (S&T) will develop new technologies to identify vulnerabilities and mitigate risks related to the global semiconductor supply chain to reduce potential disruptions and security threats.

2) Cybersecurity: Ensuring the cybersecurity of microelectronics is crucial due to the potential for hardware vulnerabilities to be exploited. Here the focus is on secure design, testing, and supply chain integrity to prevent attacks and breaches.

18

3) Microelectronics Quantifiable Assurance (MQA): development of metrics for security verification of parts and systems. 3.2.2.5. Department of Homeland Security (DHS) Semiconductor and Microelectronics gaps and opportunities

1) Intellectual Property (IP) Protection: IP theft protection is also a concern to safeguard innovation.

2) Export Controls: The U.S. government regulates the export of certain semiconductor technologies to prevent potential adversaries from accessing sensitive technologies that could have military applications.

3) Environmental Impact: The government encourages the development of environmentally friendly practices in semiconductor manufacturing, aiming to reduce the environmental footprint of the industry.

19 3.2.3. National Institute of Standards and Technology (NIST) 3.2.3.1. NIST Mission To promote U.S. innovation and industrial competitiveness by advancing measurement science, standards, and technology in ways that enhance economic security and improve our quality of life. https://www.nist.gov/about-nist 3.2.3.2. NIST Semiconductor and Microelectronics Standards (SMS) Goals Promote U.S. innovation and industrial competitiveness in the semiconductor industry, administer the CHIPS for America program successfully, and help the US achieve its goal of becoming a global leader in semiconductor manufacturing. 3.2.3.3. NIST Participation in Standards Developing Organizations (SDOs) that are related to SMS

- IEEE o C006 - Board Of Governors o Electromagnetic Shielding Enclosures (WG299) o C63 - Electromagnetic Compatibility o TC-10 - Waveform Generation, Measurement And Analysis o N42.38 - Performance Criteria For Spectroscopy Based Portal Monitors Used For Homeland Security o N42.49 - Performance Criteria For Personal Emergency Radiation Detectors (perds) For Exposure Control o MEMS – Microelectronmechanical Systems Standards Sponsor Committee o C63.27 - Evaluation Of Wireless Coexistence o APS/SC - Antennas and Propagation Standards Committee o IEEE P1900.8 - Machine Learning For Rf Spectrum Awareness In Dynamic Spectrum Access (DSA) And Sharing Systems (COM/DYSPAN-SC/MLSA)

## (IEEE P1900.8)

o TC9.P1451.5.10 - Standard for a Smart Transducer Interface for Sensors and Actuator -- Wireless Communication Protocols and Transducer Electronic Data Sheet (TEDS) NB-IoT Protocol Working Group (NB-IoT Protocol WG)

- ISO and ISO/IEC o (ISO/IEC) JTC 1/SC 37 - Biometrics o (ISO) TC 213/WG 6 - General Requirements For Geometrical Product Specification (GPS) Measuring Equipment o (ISO) TC 201/SC 6 - Secondary Ion Mass Spectrometry o (ISO) TC 213/WG 16 - Areal and Profile Surface Texture o (ISO) TC 213 - Dimensional and Geometrical Product Specifications and

20 Verification o (ISO) ISO/TC 201/SC 10 - X-ray Reflectometry (XRR) and X-ray Fluorescence (XRF) Analysis

- IEC o TC 29/WG 5 - Working Group: Measurement Microphones

- ASTM International (formerly known as American Society for Testing and Materials) o Committee F42 on Additive Manufacturing Technologies

- Semiconductor Equipment and Materials International (SEMI) o Wafer Bond o MEMS Reliability WG o C009 North America Region Standards Committee o Inspection And Metrology Task Force o C012 Gases o C007 Liquid Chemicals o Photovoltaic o C001 Silicon Wafer o Bonded Wafer Stack Task Force o Technical Architect Board o Traceability Committee o 3DS-IC Three Dimensional Stacked Integrated Circuits o C010 Microlithography o SC.01 Materials Characterization o SC.01 Patterning Committee o TF.01 Advanced Surface Inspection o C018 Compound Semiconductor Materials o TF.02 Line Edge Roughness o C033Anti-counterfeiting Workgroup o MEMS/NEMS Micro-electro-mechanical Systems/nano-electro-mechanical Systems o TF.05 Overlay Metrology Specifications

- ASTM International (formerly known as American Society for Testing and Materials) o Committee F42 on Additive Manufacturing Technologies

- SAE International o CE-12 - Solid State Devices

- IPC – Association Connecting Electronics Industries o PERM - Perm - Pb-free Electronics Risk Management o 7-11 - Test Methods o IPC-2252 Task Group (D-21B) o High Speed/high Frequency Controlled Impedance (D-21C) o D-21 - High Speed/high Frequency Design o D-24 - High Speed/high Frequency Test Methods o Product Data Exchange Task Group (2-15A) o Product Design Configuration Exchange Task Group (2-15E) o Product Manufacturing Quality Exchange Task Group (2-15D) o 2-15 - Supply Chain Communication Subcommittee o Product Genealogy Exchange Task Group (2-15C)

21 o D-54 - Embedded Devices Test Methods o D-50 - Embedded Components Committee o D-70 - E-Textiles Committee o D-74a - Printed Electronics E-Textiles Electrical Test Task Group o D-74 - E-Textile Test Methods Development and Validation Subcommittee

- International Technology Roadmap for Semiconductors (ITRS) o Metrology Technical Working Group o Emerging Research Materials 3.2.3.4. NIST Semiconductor and Microelectronics focus areas and priorities

- Chiplets o A chiplet is an integrated circuit that contains a subset of functionality and can be combined with other chiplets in a single package to create a larger, more powerful chip, which provides several advantages over a traditional system on chip such as reusable IP and reduced cost via heterogeneous integration.

- Interconnects – The connections between several specialized, smaller semiconductor devices within a package to create a system-in-package (SiP)

- Packaging – Generally, packaging is the encapsulation of an integrated circuit in a specially designed housing. For chiplets, it is a method of creating complex integrated circuits by combining modular chips, each with specialized functionality

- Interoperability – The ability of chiplets from different providers to work together seamlessly within a system. The goal is to create a system comprised of chiplets that can function together as a single unit, regardless of the source of the individual chiplets.

- Metrology and Measurement Science

- Materials Purity and Properties – New metrology is needed to meet increasingly stringent requirements for semiconductor material purity, physical properties, and provenance. This involves the journey of a material from production to end use. (https://fedtechmagazine.com/article/2022/11/nist-outlines-7-opportunities-ussemiconductor-manufacturing)

- Future Microelectronics Manufacturing – Future microelectronics manufacturing involves the development of new measurement methods, data, reference artifacts, models, and theory to enable higher device yields and reliability, lower costs, improved fabrication, and performance¹. Advances in measurement science, standards, materials, instrumentation, testing, and manufacturing capabilities will be needed to help design, develop and manufacture next-generation microelectronics¹.

22 (https://www.nist.gov/semiconductors)

- Advanced Packaging – Advanced packaging refers to the integration of separately manufactured components. Advanced packaging is a key area of focus in chiplet technology. It allows for the assembly of various types of third-party chips such as I/Os, memory, and processor cores in a package. (https://www.nist.gov/news-events/news/2022/09/nist-report-outlines-strategicopportunities-us-semiconductor-manufacturing)

- Digital Twin – o A digital twin is a virtual representation of a physical object or system that is created with collected data and updated with real-time data. A digital twin needs data about an object or process to create a virtual model that can mimic the behaviors or states of the real-world item or procedure. This data may cover the entire lifecycle of a product and include design specifications, production processes, or engineering information. Digital twins can help accelerate the chip design and manufacturing process, improve performance without affecting full-capacity operations, and enable solutions such as predictive maintenance and optimized scheduling and dispatch.

- Manufacturing process and equipment management – Manufacturing process and equipment management is the use of a virtual model of a physical manufacturing process to analyze the production performance. It uses real-time data from sensors and other source.

- Quality control – Quality control is the use of a virtual model of a real-world product or service to ensure that it meets the expected requirements. It uses real-time data from sensors and other sources to create a dynamic replica of the physical product or service. It is used to prevent and detect defects, reduce waste, and improve customer satisfaction.

- Supply chain management and assurance – Supply chain management and assurance is the use of a virtual model of a the real-world supply chain and its processes. It uses real-time data from sensors and other sources to create a dynamic replica of the physical supply chain and its components. It can help improve supply chain visibility, traceability, security, and sustainability. 3.2.3.5. NIST Semiconductor and Microelectronics gaps and opportunities

- NFPA Semiconductor and Related Facilities – NIST participates in the NFPA in other capacities, but the NFPA Semiconductor and Related Facilities committee could use the expertise of NIST personnel.

- Chiplets open standards and de facto standards organizations The leading organizations that are standardizing chiplets usage and interoperability are trending towards being private enterprises. Organizations, such as the UCIe, bunch of

23 wires (BoW), OpenHBI, and OIF XSR, are made up of private companies and entities and usually government involvement is not allowed. The Federal government could seek, or continue to pursue, membership opportunities in these organizations to assist in the forward movement of chiplets standardization.

24 3.2.4. US Air Force 3.2.4.1. US Air Force Mission The mission of the United States Air Force is to fly, fight and win - airpower anytime, anywhere. Whether full time, part time, in or out of uniform, everyone who serves plays a critical role in helping us achieve mission success. https://www.airforce.com/mission 3.2.4.2. US Air Force Semiconductor and Microelectronics Standards (SMS) Goals No specific goals at this time. 3.2.4.3. US Air Force Participation in Standards Developing Organizations (SDOs) that are related to SMS

- JFAC

- DAPRA SPADE

- IEEE

- JEDEC

- NIST 3.2.4.4. US Air Force Semiconductor and Microelectronics focus areas and priorities Secure Edge Compute, Quantum Computing, AI Hardware at the Edge, Leap Ahead Manufacturing, 5G/6G Hardware, Electronic Warfare, Anti-Tamper Security, Cryptography, Microelectronics Assurance, Trusted Supply Chain 3.2.4.5. US Air Force Semiconductor and Microelectronics gaps and opportunities

- High fidelity system/mission models

- Holistic secure processors

- Trusted supply chain

- IP validation and interoperability

- Rapid Certification

- Obsolescence

25 3.2.5. US General Services Administration (GSA) 3.2.5.1. United States General Services Administration (GSA) Mission To deliver the best customer experience and value in real estate, acquisition, and technology services to the government and the American people. https://www.gsa.gov/about-us/mission-and-background 3.2.5.2. United States General Services Administration (GSA) Semiconductor and Microelectronics Standards (SMS) Goals The mission of GSA requires that the products GSA contracts for conform to standards for reliability, safety, and security to ensure our Government customers receive quality products. Many of the product’s GSA is responsible for include semiconductor and microelectronics components. It is advantageous for GSA to promote U.S. innovation and industrial competitiveness in the microelectronics industry, and help the US achieve its goal of becoming a global leader in semiconductor and microelectronics manufacturing to ensure supply chain availability and high quality of critical components so GSA can provide secure, reliable, quality products to customers. 3.2.5.3. United States General Services Administration (GSA) Participation in Standards Developing Organizations (SDOs) that are related to SMS. Please note that due to the short timeframe required for input, this list may not be comprehensive. GSA will continue to review participation in SDOs and provide updates as appropriate.

- IEEE: Institute of Electrical and Electronics Engineers

- IPC

- UL 3.2.5.4. United States General Services Administration (GSA) Semiconductor and Microelectronics focus areas and priorities

- Currently GSA is focused on development and revision of standards for microelectronics manufacturing that will help to ensure the security and reliability of the components and systems.

- Supply chain issues to ensure availability and security of components.

## NIST IR 8501

December 2023 26 3.2.5.5. United States General Services Administration (GSA) Semiconductor and Microelectronics gaps and opportunities GSA is not currently aware of existing gaps or opportunities.

27 3.2.6. US Navy 3.2.6.1. United States Navy (USN) Mission The United States is a maritime nation, and the U.S. Navy protects America at sea. Alongside our allies and partners, we defend freedom, preserve economic prosperity, and keep the seas open and free. Our nation is engaged in long-term competition. To defend American interests around the globe, the U.S. Navy must remain prepared to execute our timeless role, as directed by Congress and the President. https://www.navy.mil/About/Mission/ 3.2.6.2. United States Navy (USN) Semiconductor and Microelectronics Standards (SMS) Goals No specific goals at this time. 3.2.6.3. United States Navy (USN) Participation in Standards Developing Organizations (SDOs) that are related to SMS

- UCIe

- DARPA SPADE

- JFAC Levels of Assurance

- JFAC FPGA Best Practices

- JFAC COTS Best Practices

- JFAC ASIC Best Practices

- JFAC Firmware Best Practices

- JFAC CIC Best Practices

- IPC D-33-ap Ultra HDI Subcommittee

- IPC 2-19b Trusted Supplier Task Group

- IPC B-10 Packaged Electronic Components Committee

- IPC B-10a Plastic Chip Carrier Cracking Task Group

- IPC Pb-Free Electronics Risk Management (PERM) Council

28 3.2.6.4. United States Navy (USN) Semiconductor and Microelectronics focus areas and priorities

- Anti-Tamper

- Microelectronics Assurance (ASIC/FPGA/Firmware)

- NIST – Evaluation of NIST standards

- Counterfeit and Supply Chain Awareness and Research 3.2.6.5. United States Navy (USN) Semiconductor and Microelectronics gaps and opportunities

- Trusted Computing Group (TCG)

- Third-party IP verification and validation for application specific integrated circuit (ASIC) and field-programmable gate array (FPGA) design

29 National Standards Strategy for Critical and Emerging Technology Strategy Recently, the Biden-⁠Harris Administration announced the National Standards Strategy for Critical and Emerging Technology (NSSCET) [1]. The NSSCET aims to ensure that the United States remains a leader in the global economy by promoting the development and use of standards for CET. The strategy focuses on four key objectives: investment, participation, workforce, and international engagement. The overall strategy calls for increased investment in pre-standardization research, translational research, and educational programs to promote innovation and workforce development in CET. It also calls for the promotion of participation by the private sector, academia, and other stakeholders in CET standards development activities. The strategy emphasizes priority areas such as Communication and Networking Technologies, Artificial Intelligence and Machine Learning, Quantum Information Technologies, Automated and Connected Infrastructure, Cybersecurity and Privacy, among others. There is alignment between the overall work of the SMSWG and NSSCET priority areas. Specifically, the NCCSET priority area:

- Semiconductors and Microelectronics, including Computing, Memory, and Storage Technologies, which affect every corner of the global economy, society, and government, and which power a panoply of innovations and capabilities. Additionally, the NSSCET defines specific applications that will impact our global economy and national security. Two of the applications align with the overall work of the SMSWG:

- Critical Minerals Supply Chains, where we will promote standards that support increased sustainable extraction of critical minerals necessary to manufacture renewable energy technologies, semiconductors, and EVs.

- Cybersecurity and Privacy, which are cross-cutting issues that are critical to enabling the development and deployment.

30 References References for Section 1 Introduction and Overview

## [1] CRITICAL AND EMERGING TECHNOLOGIES LIST UPDATE

https://www.whitehouse.gov/wp-content/uploads/2022/02/02-2022-Critical-and-Emerging- Technologies-List-Update.pdf

## [2] UNITED STATES GOVERNMENT NATIONAL STANDARDS STRATEGY FOR CRITICAL AND EMERGING TECHNOLOGY

https://www.whitehouse.gov/wp-content/uploads/2023/05/US-Gov-National-Standards-Strategy- 2023.pdf References for Section 2 Recommendations to the ICSP for Strategic Standards Priority Areas [1] JEDEC Solid State Technology Association: A global leader in developing open standards for the microelectronics industry.: https://www.jedec.org/ [2] Society of Automotive Engineers: A professional organization for mobility engineering professionals in the aerospace, automotive, and commercial vehicle industries.: https://www.sae.org/ [3] IPC: Association Connecting Electronics Industries: A trade association that provides standards, training, and certification programs for the electronics manufacturing industry.: https://www.ipc.org/ [4] IEEE: The world's largest technical professional organization dedicated to advancing technology for the benefit of humanity.: https://www.ieee.org/ [5] ESD Association: A professional voluntary association dedicated to advancing the theory and practice of electrostatic discharge (ESD) avoidance.: https://www.esda.org/ [6] ASTM International: An international standards organization that develops and publishes technical standards for a wide range of materials, products, systems, and services.: https://www.astm.org/ [7] International Organization for Standardization (ISO): An independent, non-governmental international organization that develops and publishes standards for a wide range of industries.: https://www.iso.org/ [8] ISO/IEC Joint Technical Committee 1 (JTC 1): A joint technical committee of ISO and IEC that develops and publishes international standards for information technology.: https://www.iso.org/organization/70.html [9] International Electrotechnical Commission (IEC): An international standards organization that prepares and publishes international standards for all electrical, electronic, and related technologies.: https://www.iec.ch/homepage

31 [10] SEMI: A global industry association that connects people, ideas, and solutions to advance electronic manufacturing.: https://semi.org/ [11] International Technology Roadmap for Semiconductors (ITRS): A collaborative effort by the global semiconductor industry to identify and address technology challenges facing the industry.: http://www.itrs2.net/ [12] American National Standards Institute (ANSI): A private non-profit organization that oversees the development of voluntary consensus standards for products, services, processes, systems, and personnel in the United States.: https://www.ansi.org/ [13] RAND Corporation: A research organization that develops solutions to public policy challenges to help make communities throughout the world safer and more secure, healthier and more prosperous.: https://www.rand.org/pubs/perspectives/PEA1394-1.html [14] Arizona State University News: An article discussing how ASU researchers are working to secure the microelectronics supply chain from cyberattacks.: https://news.asu.edu/20220331securing-microelectronics-supply-chain [15] Center for Security and Emerging Technology (CSET): A research organization that studies the security implications of emerging technologies.: https://cset.georgetown.edu/publication/thesemiconductor-supply-chain [16] Survey of secure processors: https://ieeexplore.ieee.org/document/8344637 [17] Microsoft Is Making a Secure PC Chip—With Intel and AMD's Help: https://www.wired.com/story/microsoft-pluton-secure-processor/. [18] Government-Industry Data Exchange Program (GIDEP): http://www.gidep.org/ [19] Semiconductor Industry Association (SIA): An industry trade group that represents U.S.based semiconductor companies on issues related to public policy, innovation, and competitiveness.: https://www.semiconductors.org/policies/anti-counterfeiting/ [20] Insight Analytical Labs: A company that provides authenticity analysis services for electronic components such as semiconductors.: https://www.ial-fa.com/authenticity-analysis/ [21] SIA Anti-Counterfeiting Whitepaper: A whitepaper discussing anti-counterfeiting measures in the semiconductor industry.: https://semiconductors.org/wp-content/uploads/2018/06/SIA- Anti-Counterfeiting-Whitepaper-1.pdf [22] IEEE Xplore Digital Library: An article discussing metrology challenges in advanced semiconductor manufacturing processes.: https://dforte.ece.ufl.edu/wpcontent/uploads/sites/65/2021/01/MTV_2013_submission_25.pdf [23] S&P Global Engineering & Research Analysis: An article discussing factors contributing to the current global semiconductor shortage.: https://www.spglobal.com/engineering/en/researchanalysis/understanding-the-current-global-semiconductor-shortage.html [24] Harvard Business Review: An article discussing how to fix the U.S. semiconductor supply chain by increasing domestic production capacity and improving supply chain resilience.: https://hbr.org/2022/10/fixing-the-u-s-semiconductor-supply-chain

32 [25] Defense Acquisition University (DAU) Acquipedia: An article discussing counterfeit electronic parts detection methods used by defense contractors.: https://www.dau.edu/acquipedia/pages/ArticleContent.aspx?itemid=747 [26] GEM Energy Management Services: A company that provides energy management services to semiconductor manufacturers.: https://gemes.com/about-gem/ [27] IEEE Electronics Packaging Society Glossary: Definition of Interconnects.: https://eps.ieee.org/technology/definitions.html [28] All About Circuits News: An article discussing innovative interconnects as a future solution for chiplet-based processors.: https://www.allaboutcircuits.com/news/innovative-interconnectsthe-future-of-chiplet-based-processors/ [29] Chiplet Technology: A New Era in Microelectronics: https://nepp.nasa.gov/docs/etw/2021/15-JUN-21_Tues/1500_Ramamurthy-Chiplet-Technologyv3.pdf [30] A 101 Guide to the Integrated Circuit Packaging Process: https://www.thomasnet.com/insights/a-101-guide-to-the-integrated-circuit-packaging-process/ [31] IEEE Electronics Packaging Society Glossary: Definition of Interconnects: https://eps.ieee.org/technology/definitions.html [32] IC Packages Types: https://www.engineersgarage.com/ic-packages-types/ [33] What are Computer Chiplets?: https://research.ibm.com/blog/what-are-computer-chiplets [34] Overview of the Microelectronics Industry: https://www.ndia.org/- /media/sites/ndia/divisions/electronics/ndia-ed-mtg-020719_jeremy-muldavin_overviewvf.ashx?la=en [35] Future of Semiconductor Performance: https://irds.ieee.org/topics/future-of-semiconductorperformance [36] NIST Semiconductor Glossary: https://www.nist.gov/semiconductors/semiconductorglossary [37] Metrology and Inspection in Semiconductor Manufacturing: https://www.hitachihightech.com/global/en/knowledge/semiconductor/room/manufacturing/metrologyinspection.html [38] NIST Semiconductor Research: https://www.nist.gov/semiconductors [39] NIST Outlines 7 Opportunities for U.S. Semiconductor Manufacturing: https://fedtechmagazine.com/article/2022/11/nist-outlines-7-opportunities-us-semiconductormanufacturing [40] NIST Report Outlines Strategic Opportunities for U.S. Semiconductor Manufacturing: https://www.nist.gov/news-events/news/2022/09/nist-report-outlines-strategic-opportunities-ussemiconductor-manufacturing [41] What is Digital Twin?: https://www.twi-global.com/technical-knowledge/faqs/what-isdigital-twin

33 [42] Leveraging the Digital Twin in Smart Microelectronics Manufacturing: https://semiengineering.com/leveraging-the-digital-twin-in-smart-microelectronicsmanufacturing/ [43] Digital Twin in Semiconductor Industry: https://blog.gramener.com/digital-twin-in-semiconductor-industry/ [44] Diminishing Manufacturing Sources and Material Shortages (DMSMS): https://www.dsp.dla.mil/Programs/DMSMS/ [45] SD-22 DoD DMSMS Guidebook: https://www.dau.edu/cop/dsp/announcements/updatedsd-22-dod-dmsms-guidebook-now-available-assist-and-quicksearch. [46] SD-26 DMSMS Contract Language Guidebook: http://everyspec.com/DoD/DoD- PUBLICATIONS/SD-26_01OCT2019_56848/. [47] The Digital Twin in Manufacturing: What You Need to Know: https://www.perforce.com/blog/vcs/digital-twin-manufacturing. [48] Digital Twins in Quality Control: https://medium.com/neurisium/digital-twins-in-qualitycontrol-what-if-you-could-predict-changes-in-quality-102a2d26311a. [49] Supply Chain Digital Twins – anyLogistix: https://www.anylogistix.com/features/supplychain-digital-twins/. [50] What is a Digital Supply Chain Twin? – AIMMS: https://www.aimms.com/story/what-is-adigital-supply-chain-twin-and-how-can-it-support-your-strategic-decisions/. References for Section 4 National Standards Strategy for Critical and Emerging Technology Strategy [1] FACT SHEET: Biden-⁠Harris Administration Announces National Standards Strategy for Critical and Emerging Technology; https://www.whitehouse.gov/briefing-room/statementsreleases/2023/05/04/fact-sheet-biden-harris-administration-announces-national-standardsstrategy-for-critical-and-emerging-technology/ [2] United States Government National Standards Strategy for Critical and Emerging Technology; https://www.whitehouse.gov/wp-content/uploads/2023/05/US-Gov-National- Standards-Strategy-2023.pdf

34 Appendix A. Semiconductors and Microelectronics Standards Working Group Establishment The Semiconductor and Microelectronics Standards Working Group (hereinafter referred to as the “SMSWG” or “Working Group”) is established under the provisions of the charter of the Interagency Committee on Standards Policy (ICSP). The ICSP advises the Secretary of Commerce and the heads of other Federal agencies in matters relating to the implementation of OMB Circular A-119 and reports to the Secretary of Commerce through the Director of the National Institute of Standards and Technology (NIST). Purpose The objective of the SMSWG is to facilitate coordination of Federal agency semiconductor and microelectronics standards (SMS) activities, respond to requests for information, and develop recommendations relating to relevant standards policy matters to the ICSP. The SMSWG reports to the Chair of the ICSP and advises the members of the ICSP on relevant issues. Functions The SMSWG is responsible for:

- Assisting the ICSP in promoting effective and consistent federal policies in the area of semiconductor and microelectronics standards.

- Providing an annual report to the ICSP on the current SMS activities of participating Federal agencies and recommendations for strategic directions in relevant Federal standards efforts.

- Responding to requests for information and advising the ICSP on effective means of coordinating SMS activities with those of the private sector.

- Sharing best practices in semiconductor and microelectronics standards among Federal agencies.

- Coordinating Federal semiconductor and microelectronics standards interests across application areas such as transportation, energy, health, public safety, and others. Organization Participants include Federal agency representatives with expertise relevant to standards in semiconductor and microelectronics. Each participating Federal entity will identify one voting member to represent the entity. The SMSWG co-chairs comprise one NIST staff member designated by the ICSP Chair and serving as secretariat, along with other co-chairs as elected by majority vote of the SMSWG members present. The Working Group will follow a similar meeting schedule as the ICSP and will meet at least three times each year. Other meetings may be called at the discretion of the co-chairs. Approval and Renewal Approved by the Interagency Committee on Standards Policy at its June 6, 2023, meeting. This charter expires three years after the date of approval unless renewed by the ICSP.

35 Appendix B. Abbreviations ACIS (Automated and Connected Infrastructure) AI (Artificial Intelligence) ASIC (Application-specific integrated circuit) C&P (Cybersecurity and Privacy) CE-11 (Passive Components) CE-12 (Solid State Devices) CET (Critical and Emerging Technology) COTS (Commercial off-the-shelf) CPI (critical program information) DARPA (Defense Advanced Research Projects Agency) DMSMS (Diminishing Manufacturing Sources and Material Shortages) EMSA (Electromagnetic Compatibility) F42 (Additive Manufacturing Technologies) FPGA (Field-programmable gate array) GEM (Generalized Emulation of Microcircuits) GIDEP (Government-Industry Data Exchange Program) ICSP (Interagency Committee on Standards Policy) IEC (International Electrotechnical Commission) IEEE (Institute of Electrical and Electronics Engineers) IMT (International Mobile Telecommunications) IPC (Association Connecting Electronics Industries)

36 ISO (International Organization for Standardization) JEDEC (Joint Electron Device Engineering Council) MCM (Multichip Module) NSSCET (National Standards Strategy for Critical and Emerging Technology) NTTAA (National Technology Transfer and Advancement Act) OEM (Original Equipment Manufacturer) OSI (Open Systems Interconnection) PERM (Perm - Pb-free Electronics Risk Management) RA (Radiation Hardness Assurance) SAE (Society of Automotive Engineers) SDO (Standards Developing Organizations) SEMI (Semiconductor Equipment and Materials International) SIG (Special Interest Group) TC (Technical Committee) WG (Working Group) XRF (X-ray Fluorescence)
