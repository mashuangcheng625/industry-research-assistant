---
candidate_id: nist-chips-1400-2
title: CHIPS Research and Development Office's Technical Standards Workshops Summary
  Report
domains:
- chip_design_eda_ip
- wafer_fabrication
- packaging_testing
source_name: National Institute of Standards and Technology
source_url: https://doi.org/10.6028/NIST.CHIPS.1400-2
document_type: government_report
published_at: '2023-01-01'
document_version: NIST.CHIPS.1400-2
authority_level: official
claim_type: government_report
doi: 10.6028/NIST.CHIPS.1400-2
license_name: NIST Technical Series public-use terms
license_url: https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications
retrieved_at: '2026-07-15T09:34:01+00:00'
content_hash: 1633e5a6338466173713d9066da420facd43c5522ca960737840e08dffdb6c0d
is_synthetic: false
---

# CHIPS Research and Development Office's Technical Standards Workshops Summary Report

## SUMMARY REPORT

CHIPS R&D Chiplets Interfaces Technical Standards Workshop December 12–13, 2023 CHIPS R&D Digital Twin Technical Standards Workshop December 14–15, 2023

CHIPS for America includes the CHIPS Program Office, responsible for semiconductor incentives, and the CHIPS Research and Development Office, responsible for R&D programs. Both sit within the National Institute of Standards and Technology (NIST) at the Department of Commerce. NIST promotes U.S. innovation and industrial competitiveness by advancing measurement science, standards, and technology in ways that enhance economic security and improve our quality of life. NIST is uniquely positioned to successfully administer the CHIPS for America program because of the bureau’s strong relationships with U.S. industries, its deep understanding of the semiconductor ecosystem, and its reputation as fair and trusted. Visit https://www.chips.gov to learn more.

## DISCLAIMER STATEMENT

Certain commercial entities, equipment, or materials may be identified in this document in order to describe an experimental procedure or concept adequately. Such identification does not imply recommendation or endorsement by the National Institute of Standards and Technology, the U.S. Department of Commerce, or any part of the United States Government, nor is it intended to imply that the entities, materials, or equipment are necessarily the best available for the purpose.

## COPYRIGHT

This document is a work of the U.S. Government and is not subject to copyright in the United States (see 17 U.S.C. § 105). Foreign rights reserved. All tables and figures in this report, unless otherwise noted, were produced by NIST and DOC employees.

## NIST CHIPS 1400-2

https://doi.org/10.6028/NIST.CHIPS.1400-2

## TABLE OF CONTENTS

Executive Summary & Introduction

## EXECUTIVE SUMMARY

The CHIPS and Science Act appropriated $50 billion to the Department of Commerce’s CHIPS for America program both to support semiconductor research and development (R&D) and to expand semiconductor manufacturing capacity in the United States. Within CHIPS for America, the mission of the National Institute of Standards and Technology’s (NIST) CHIPS Research and Development Office (CHIPS R&D) is to accelerate the development and commercial deployment of foundational semiconductor technologies by establishing, connecting, and providing access to domestic research efforts, tools, resources, workers, and facilities. A key element in achieving these CHIPS R&D goals is to accelerate the private sector-led development and deployment by industry of effective technical standards. CHIPS R&D has developed a comprehensive standards roadmap that aligns with the needs of private sector semiconductor standards efforts, the requirements of CHIPS legislation, and the provisions of the U.S. Government National Standards Strategy for Critical and Emerging Technologies (USG NSS CET)1 . The CHIPS R&D standards roadmap is centered on a vision for a vibrant microelectronics standards ecosystem that is smarter, faster, and more inclusive and agile in enabling innovation. CHIPS R&D has undertaken a series of events to solicit the global semiconductor industry’s perspectives on, and input into aligning the government effort with the industry’s technical standards needs. The first of these CHIPS R&D standards activities was a Standards Summit event held in September 2023, in Washington, D.C., (1st Summit), which brought together private sector thought leaders to identify strategic technical standards priorities for the semiconductor sector. Five major technical strategic standards priorities emerged from that Summit2 , including:

- Chiplets

- Digital Twins

- Data Interoperability

- Supply Chain Security and Resilience

- Advanced Packaging and Heterogeneous Integration In December 2023, two follow-on CHIPS R&D Technical Standards Workshops were organized with the goal of identifying specific standards needs within the first two of the priority areas identified in the 1st Summit: Chiplets and Digital Twins. The first, the CHIPS R&D Chiplets Interfaces Technical Standards Workshop, focused on the role of technical standards for physical and logical interfaces in enabling chiplet-based architectures in the semiconductor and microelectronics industry. The second, the CHIPS R&D Digital Twin Technical Standards Workshop, focused on the role of technical standards for digital twins to support reliable, resilient, secure, and high-quality manufacturing processes and to enable trusted supply chains. These workshops were held as hybrid virtual and in-person events at the NIST National Cybersecurity Center of Excellence (NCCoE) in Rockville, Maryland. Because of the strong subject and audience overlap of the two workshops, they were organized by a joint planning committee comprised of representatives from industry and NIST, as listed in Appendix A. The Chiplets Interfaces Workshop attracted a total of 320 attendees, made up of 60 in-person and 260 virtual participants, while the Digital Twin Workshop attracted a total of 242 attendees, comprised of 63-in-person and 179 virtual participants, respectively. Most (approximately 60 %) of the participants were from the semiconductor

industry, but the workshop also attracted strong participation from academia; standards setting / development organizations (SSO / SDO); start-ups, small and medium sized companies (SMEs); industry alliances; US National Laboratories; and government employees. The workshops featured a mix of panel and keynote presentations from renowned experts in the field, followed by breakout discussions that identified the technical gaps and standards opportunities. The rankings of the top priority technical standards gaps identified by participants in the respective workshops are as follows: Chiplets Interfaces Technical Standards Gaps:

1. System optimization (modeling, simulation, and testing, standards)

2. Security and traceability testing standards

3. General testing and verification standards (outside of security)

4. Interconnection protocol

5. Chiplet abstraction (e.g., process design kit (PDK))

6. Reliability and failure analysis standards Digital Twin for Semiconductor Manufacturing Technical Standards Gaps:

1. Interoperability (data models, digital twin interfaces, digital twins communicating with other digital twins)

2. Digital twin taxonomy and definitions

3. Security (data provenance, traceability, digital thread)

4. Existing standards (database of standards, analysis of standards, governance)

5. Testing, validation, verification (reliability testing, uncertainty verification, benchmarks testing, methodologies, creation of new metrics)

6. Develop benchmarks and metrics models to specific use cases. In addition to the identification of the top standards gaps, workshop participants made broad recommendations for the semiconductor chiplets and digital twins standards communities. Some of the key recommendations are listed below.

- Collaboration among SSOs/SDOs through an alliance of existing organizations is needed to develop the identified technical standards.

- Incentives to stimulate collaboration between SSOs/SDOs are needed (e.g., a private-public partnership model).

- Standards education must be emphasized at all levels in the semiconductor supply chain.

- Further standards identification is needed to flesh out the specific standards needed within the top three technical standards gap categories identified for digital twins.

- Existing standards must be critically assessed for chiplet interfaces and digital twins to avoid duplication of efforts.

- Chiplets as a use case for digital twin standards development is recommended. This report also provides additional information about the two workshops, including more-detailed descriptions of the identified standards, priority areas, and recommendations that emerged from the discussions.

## INTRODUCTION CHIPS FOR AMERICA

The CHIPS and Science Act3 appropriated $50 billion to the Department of Commerce’s CHIPS for America program, both, to support semiconductor research and development (R&D) and to expand semiconductor manufacturing capacity in the United States. This includes $39 billion for the Department of Commerce (the Department) to expand domestic semiconductor manufacturing capacity through the incentives program and $11 billion to advance U.S. leadership in semiconductor R&D. R&D advances will be realized through four programs: the National Semiconductor Technology Center (NSTC), the National Advanced Packaging Manufacturing Program (NAPMP), the CHIPS Metrology Program, and a Manufacturing USA institute. These investments, across both the R&D and incentives programs, seek to strengthen U.S. competitiveness, support domestic manufacturing and innovation, and create good jobs across the country.

## CHIPS R&D MISSION AND GOALS

Within CHIPS for America, the mission of the National Institute of Standards and Technology’s (NIST) CHIPS Research and Development Office (CHIPS R&D) is to accelerate the development and commercial deployment of foundational semiconductor technologies by establishing, connecting, and providing access to domestic research efforts, tools, resources, workers, and facilities. CHIPS R&D aims to achieve the following goals by 2030:

- U.S. Technology Leadership: The United States establishes the capacity to invent, develop, prototype, manufacture, and deploy the foundational semiconductor technologies of the future.

- Accelerated Ideas to Market: The best ideas achieve commercial scale as quickly and cost effectively as possible.

- Robust Semiconductor Workforce: Inventors, designers, researchers, developers, engineers, technicians, and staff meet evolving domestic government and commercial sector needs. A key to achieving these CHIPS R&D goals is to accelerate the private sector-led development and deployment of effective pertinent technical standards.

## BACKGROUND FOR CHIPS R&D STANDARDS EFFORT

CHIPS R&D has developed a comprehensive standards roadmap in response to calls from the private sector for semiconductor standards efforts, the requirements of CHIPS legislation, and the provisions of the United States Government National Standards Strategy for Critical and Emerging Technologies (USG NSS CET)i , as summarized below:

- Standards were identified by private sector stakeholders as a core competency for CHIPS R&D. Both the need for standards and ensuring that standards align across different stakeholders were highlighted in many of the responses to NIST’s request for information to guide the design of CHIPS programs4 .

- The CHIPS Act5 provision (15 USC §4656 (e)) copied below, specifies that private-sector-led technical standards for the semiconductor industry should be an integral part of the CHIPS R&D strategy: “the Director of the National Institute of Standards and Technology shall carry out a microelectronics research program to enable advances and breakthroughs in measurement science, standards, material characterization, instrumentation, testing, and manufacturing capabilities that will accelerate the underlying research and development for metrology of next generation microelectronics and ensure the competitiveness and leadership of the United States within this sector” (emphasis added).

- The CHIPS and Science Act (42 USC §18951(a)) specifies guiding principles for standards, which include: (1) openness, transparency, due process, balance of interests, appeals, and consensus in the development of international standards are critical; (2) voluntary consensus standards, developed through an industry-led process, serve as the cornerstone of the United States standardization system and have become the basis of a sound national economy and the key to global market access; (3) strengthening the unique United States public-private partnerships approach to standards development is critical to United States economic competitiveness; and (4) the United States Government should ensure cooperation and coordination across Federal agencies to partner with and support private sector stakeholders to continue to shape international dialogues in regard to standards development for emerging technologies.

- The United States Government National Standards Strategy for Critical and Emerging Technologies (USG NSS CET) has four major objectives for CETs, including semiconductors and microelectronics: investment, participation, workforce, and integrity and inclusivity.

## CHIPS R&D

Standards Roadmap

## CHIPS R&D STANDARDS ROADMAP VISION

The vision of the CHIPS R&D Standards Roadmap is for: A vibrant microelectronics standards ecosystem that is smarter, faster, and more inclusive and agile in enabling innovation. This vision provides for working with the semiconductor standards sector in enhancing strategic focus, matching the pace of standards development to the pace of innovation in the semiconductor sector, expanding opportunities for participation in standards activities, and responding effectively to the needs of industry.

## MISSION

The mission of the CHIPS R&D standards effort comprises six elements as follows.

- Support private sector leadership.

- Focus on strategic priorities.

- Open and accelerate the standards innovation pipeline.

- Support education, awareness, and workforce development.

- Align government efforts.

- Partner with allies.

## OUTCOMES

Implementation of the CHIPS R&D Standards Roadmap is intended to achieve the following outcomes.

1. Standards at the speed of innovation,

2. A standards-enabled global market,

3. Standards as innovation platforms,

4. Inclusive standards leadership,

5. Education for career opportunities in standards development, and

6. A diverse standards-capable workforce. In pursuing these outcomes, the CHIPS R&D standards effort is intended to:

- Enhance U.S. economic security through standards that support innovation, collaboration, and a vibrant domestic landscape of small, medium, and large corporations;

- Support national security through standards that underpin a domestic semiconductor industry that is resilient, reliable, secure, and a global leader in semiconductor technologies; and

- Enable future innovation through standards that provide for interoperability, set out powerful measurement capabilities, and establish effective testing and assurance methods that spur adoption of new technologies.

## CHIPS R&D

Workshops: Introduction and Overview

## CHIPS R&D WORKSHOPS: INTRODUCTION AND OVERVIEW

Achieving CHIPS R&D’s goals will require cooperation and collaboration across the private sector standards setting organizations serving the semiconductor standards landscape. As such, CHIPS R&D has undertaken a series of activities, including but not limited to open workshops, to solicit the global semiconductor industry’s perspectives on, and input into aligning the government effort with the industry’s technical standards needs. The first of these CHIPS R&D standards activities was a Standards Summit event held in September 2023, in Washington, D.C., (1st Summit), which brought together private sector thought leaders to identify strategic technical standards priorities for the semiconductor sector. During the 1st Summit, there was significant discussion about the expanding roles of chiplets and digital twins as emerging technology enablers in the semiconductor industry. As a follow up to the 1st Summit, two one-and-a-half-day hybrid technical standards workshops were held in December 2023 that brought together technical experts to identify community priorities for chiplets interfaces and digital twin technical standards. The Chiplets Interfaces Workshop attracted a total of 320 attendees, made up of 60 in-person and 260 virtual participants, while the Digital Twin Workshop attracted a total of 242 attendees, comprised of 63-in-person and 179 virtual participants, respectively. Most of the participants were from the semiconductor industry (approximately 60 %), but the workshop also attracted strong support and participation from academia, standards setting organizations, industry alliances, and government. The workshops were planned by an organizing committee comprising leaders from SSOs, industry, and government representatives (see Appendix A). Structurally, the workshop agendas (provided in Appendix B and

## C) contained a mix of keynote and plenary sessions that were designed to seed discussions in the corresponding

breakout sessions. The invited keynote speakers and panelists provided insights and identified key challenges in each of the topic areas to stimulate conversations in the subsequent breakout sessions. During the moderated breakout sessions, the workshop participants reflected on the speaker insights, discussed the questions provided by the planning committee, and identified gaps and technical standards opportunities to address critical challenges facing implementation of chiplets and digital twins in the semiconductor manufacturing industry. The approach used to capture input from participants to inform this report is described in Appendix D.

CHIPS R&D Chiplets Interfaces Technical Standards Workshop

## CHIPS R&D CHIPLETS INTERFACES TECHNICAL STANDARDS WORKSHOP

Chiplets refer to small, partially functional, semiconductor chips that, when assembled at tight pitch and close to one another, result in a highly functional subsystem. Chiplets can serve as a processor core, memory block, input output (I/O) driver, or signal processing unit. By dividing the chip into discrete units and linking them with a standardized interface, chiplets empower designers to address challenges in performance, efficiency, power consumption, size, and cost. Chiplets enhance chip yields and cost-effectiveness while delivering the performance of a large, unified chip. Designers can customize system on a chip (SoC) and heterogeneously integrated chips by mixing and matching chiplets, selecting the most suitable process technologies for individual functions, leveraging chiplet intellectual property (IP), streamlining transitions to new process nodes, and minimizing waste and manufacturing defects. Chiplets play a crucial role in creating the highly dense, high-performance chips essential for today's applications such as networking, storage, artificial intelligence / machine learning (AI/ML), analytics, media processing, high-performance computing (HPC), and virtual reality. The CHIPS R&D Chiplets Interfaces Technical Standards Workshop was focused on the role of technical standards for physical and logical interfaces in enabling chiplet-based architectures in the semiconductor and microelectronics industry. The specific goals and outcomes for the workshop included:

- Gaining insight from industry leaders, standard organizations, and experts in the field of chiplets.

- Identifying priorities for chiplets interface standards, as well as efforts in semiconductors and microelectronics.

- Engaging the semiconductor and microelectronics community and building a network of stakeholders.

- Providing input to standards and measurement programs supporting the needs of the semiconductor industry. The workshop agenda (Appendix B) was comprised of keynote and panel presentations that were followed by a series of breakout sessions in which the attendees had the opportunity to reflect on and discuss the ideas from the presentations, as well as provide their own input regarding the current state of chiplets interfaces in practice. The design of the workshop centered on four topic areas, starting from providing a basic understanding of chiplets and building toward the overall goal of identifying industry technical standards priorities for chiplet interface design and realization. A summary of the four areas is provided below:

1. Tutorial on Chiplet Interface Design — The introductory sessions level-set the workshop participants with a basic understanding of chiplet interface design, utilization, and current standards activities related to the realization and manufacturing of chiplets. Examples of the discussion topics ranged from the primary applications using chiplets (e.g., HPC and AI) to the standards needed for heterogeneous integration (e.g., testing and security) as well as existing standards efforts for chiplets interfaces [e.g., Universal Chiplet Interconnect Express (UCIe) and Bunch of Wires (BOW)].

2. State-of-the-Art of Chiplet Interface in Design / Manufacturing — In these sessions, panelists and participants discussed how chiplet interface design and standards are used today and the challenges

with increasing adoption in the semiconductor industry. Examples of the discussion topics included the expansion of the chiplet ecosystem through heterogeneous integration; the importance of chiplet verification, testing, and failure analysis; and the chiplet interface challenges in packaging and assembly.

3. Current State of Research in Chiplets — The third area focused on identifying current research activities for chiplet interface design, integration, and packaging that could benefit from standardization efforts. Examples of the research areas discussed included photonics packaging, modeling as a tool to overcome heterogeneous chiplet integration challenges, and security platforms for chiplets.

4. Chiplet Interface Standards Gaps — The fourth topic area focused on summarizing and debating the technical standards gaps that emerged during the three prior topic area discussions for further prioritization and to begin identifying strategies for addressing the priorities. The fourth topic area led to the final breakout sessions of the workshop in which open discussions and polling techniques were used to refine the list of industry’s top priorities for chiplets interfaces technical standards. The collective participant feedback was used to generate a rank-ordered list of the top priority chiplet interface standards areas to pursue (Appendix E). Strategies involving potential SSOs/SDOs and volunteers who could help to create new standards for the priority areas were also discussed. The top six priority areas identified by participants are described in the next section.

## STANDARDS PRIORITIES FOR CHIPLETS INTERFACES

The top six priorities identified by the workshop participants, in ranked order, included:

- System Optimization (Modeling, Simulation, and Testing Standards)

- Security, Traceability, Testing, and Standards

- General Testing and Verification Standards (Outside of Security)

- Interconnection Protocol

- Chiplet Abstraction

- Reliability and Failure Analysis Standards

1. System Optimization (Modeling, Simulation, and Testing Standards) The top recommended priority area was to creating benchmarks for system optimization through modeling, simulation, and standardized testing. System optimization requires chiplet exchange standards that comprehend the physical, electrical signal integrity, power, mechanical, thermal, test, and security requirements and specifications. There is a gap in modeling, simulation, and testing standards, which need to move from “prediction” to “optimization". It was suggested that AI has the potential to transform microelectronics, though is not yet fully implemented, mainly due to data-sharing challenges, e.g., who owns the data on which the optimization of a custom chiplet system depends. The process of improving the performance, reliability, and efficiency of a system (i.e., co-optimization) must preserve some degree of freedom in each segment of the design, not just within chip. Besides the chiplet specifications already described other technical specifications that need optimization include the form factor, physical chip layout (e.g., geometry), thermal modeling, and thermal management.

2. Security and Traceability Testing Standards Protocols need to be established for security and traceability to enhance chip integrity. Security aware, chiplet-based system-on-chip (SoC) architectures require chiplet interface base designs that incorporate built-in test, security interoperability, reliability, and repair capabilities, and a detailed understanding of the substrate processes from the third-party vendor. The ‘certain security’ standards for SoC / heterogeneous integration should comply with the many existing insular standards (e.g., authentication, encryption, etc.) and protocols for chip security, as well as meet the specification of the holistic package co-design. Other gaps include standards for traceability, and bill of- and provenance of materials.

3. General Testing and Verification Standards (Outside of Security) Universal testing and verification standards and protocols beyond security aspects need to be developed. One use-case that was highlighted was a requirement to find, extract, and repair defective chiplets in heterogeneous integrated systems. This requires a functional test that will show the approximate location of the defective die. Also, the development of a ‘fail-fast’ protocol could pinpoint the root cause of the failure that was not captured during assembly and test.

4. Interconnection Protocol Realizing the full potential of chiplet-based architectures will work only if the community can create an interface that allows mixing and matching of chiplets and substrates. A standardized interconnection protocol to streamline chip communication / interoperability needs to be defined. Current ecosystem-specific standards/ guidelines, (e.g., UCIe, BoW etc.) need to be harmonized to allow inter-ecosystem communication / plug and play.

5. Chiplet Abstraction In heterogeneous integrated (HI) circuits, program execution models (PXMs) enable programmability, performance, and separate the roles of the different chiplets, while maintaining common system level models (i.e., abstraction) for program execution6 . This also moves some hardware-related optimizations to higher levels of abstraction, thus providing a means to standardize and control the dissemination of sensitive hardware-related information7 . Standards for chiplet abstraction, such as a a full Process and Assembly Design Kit (PADK), were identified as an important gap. Packaging was cited as one use-case that needs an abstraction – an abstraction model for package / assembly design kit (i.e., how many chiplets can be stacked, etc.) – that enables the weighing of tradeoffs between placement, assembly rules, thermal/mechanical constraints, signal integrity, etc. To be effective, the design kit must have an adequate level of technical specificity. A process and assembly design kit for an HI system can incorporate and abstract the key performance indicators of its component chiplets and interfaces, providing a single and unambiguous source of truth.

6. Reliability and Failure Analysis Standards Developing standards for reliability assessments and failure analysis procedures was also highlighted as an important need for chiplets. One need is for standards that enable early and frequent, non-destructive failure analysis as SoCs are being built. Another example is standards to assess the reliability of communication between dies on silicon, which may fail requiring more agile and iterative root cause analyses, defect identification, and attribution. Current reliability models for chiplets are not predictive because failure analysis results and material properties characterization data are not widely available. Therefore, automated interchange standards that enable computers and organizations to exchange information using a defined format and structure are also needed. Such standards would enable AI support in failure analysis by creating an immutable datasheet that cannot be changed through physical or cyber means.

## CHIPS R&D

Digital Twin Technical Standards Workshop

## CHIPS R&D DIGITAL TWIN TECHNICAL STANDARDS WORKSHOP

A digital twin is a virtual counterpart or simulation of a tangible entity, whether it's an object, a system, or a procedure. It serves the purpose of assessing and forecasting real-time performance. In the realm of semiconductor design and manufacturing, a digital twin proves invaluable for tasks like monitoring, diagnosing issues, refining operations and maintenance routines, and minimizing downtime and manual interventions. Critical necessities for advancing digital twin technologies include establishing standards that foster innovation. These standards encompass aspects such as data compatibility, interoperability, and modularity among hierarchical models. Additionally, they address the interfaces linking data, equipment, processes, and business management systems, as well as methodologies for the testing, validation, and verification of digital twins. The CHIPS R&D Digital Twin Technical Standards Workshop focused on the role of technical standards for digital twins to support reliable, resilient, secure, and high-quality manufacturing processes, and enabled trusted supply chains. The specific goals and outcomes for the workshop included:

- Gaining insight from industry leaders, standard organizations, and experts in the field of digital twins in semiconductor manufacturing.

- Identifying priorities for digital twin standards, as well as efforts in semiconductors and microelectronics.

- Engaging the semiconductor and microelectronics community and building a network of stakeholders.

- Providing input to standards and measurement programs supporting the needs of the semiconductor industry. The workshop agenda (Appendix C) was comprised of keynote and panel presentations that were followed by a series of breakout sessions in which the attendees had the opportunity to reflect on and discuss the ideas from the presentations, as well as provide their own input regarding the current state of digital twins in practice in semiconductor manufacturing. The design of the workshop centered on four topic areas, starting from providing a basic understanding of digital twins and building toward the overall goal of identifying industry technical standards priorities for digital twins in semiconductor manufacturing. A summary of the four areas is provided below.

1. Tutorial on Digital Twin Standards — The purpose of the first sessions was to level-set the workshop participants with a basic understanding of digital twin definition, utilization, and current standards activities related to semiconductor manufacturing. The discussion topics ranged from the primary applications using digital twins today (e.g., semiconductor manufacturing equipment maintenance and monitoring) to the universal requirements for digital twins (e.g., data provenance and management) as well as existing standards efforts for digital twins [e.g., International Organization for Standardization (ISO) and IPC frameworks].

2. State-of-the-Art of Digital Twins in Semiconductor Manufacturing — The second area centered on how digital twins and standards are used today and the challenges with increasing adoption in the semiconductor industry. Examples of the discussion topics included the use of AI/ML for expanding digital twin capabilities, secure data platforms for digital twins across the semiconductor supply chain, and the use of digital twins as virtual test environments in manufacturing.

3. Current State of Research for Digital Twins — The third area focused on identifying current research activities for digital twin technologies to support semiconductor manufacturing that could benefit from standardization. Examples of the research topics discussed included multi-physics modeling and co-design in digital twins, federated data processing as a potential enabler for industry-wide collaboration, and the feasibility of large scale, manufacturing system-level digital twins.

4. Digital Twins Standards Gaps — The fourth topic area focused on summarizing and debating the technical standards gaps that emerged during the three prior topic area discussions for further prioritization and to begin identifying strategies for addressing the priorities. The fourth topic area led to the final breakout sessions of the workshop in which open discussions and polling techniques were used to refine the list of industry’s top priorities for digital twins technical standards. The collective participant feedback was used to generate a rank-ordered list of the top priority digital twin standards areas to pursue (Appendix F). Strategies involving potential SSOs/SDOs and volunteers who could help to create new standards for the priority areas were also discussed. The top six priority areas identified by participants are described in the next section.

## STANDARDS PRIORITIES FOR DIGITAL TWINS IN SEMICONDUCTOR MANUFACTURING

The top six priorities identified by the workshop participants, in ranked order, included:

- Interoperability

- Digital Twin Taxonomy and Definitions

- Security

- Testing, Validation, and Verification Standards

- Existing Standards

- Developing Benchmarks and Metrics Models to Specific Use Cases

1. Interoperability (Data Models, Digital Twin Interfaces, Digital Twin Communication with Other Digital Twins) The need for standards that enable appropriate data sharing while both preserving the security and integrity of the data and protecting intellectual property rights emerged as a critical need. Shared data can enable optimization across complex processes, enhance operational efficiency, enable traceability and assurance, provide for interoperability, and enable innovation, among other benefits. Standards such as data taxonomies can provide a means for data sharing and interoperability. An interest here is on cultivating an ecosystem where third-party entities can leverage standardized tools and software, promoting a more integrated and efficient semiconductor landscape. As noted in a recent publication8 , the existing Open Platform Communications Unified Architecture (OPC UA)9 standard should be considered to solve the problem of interoperability in digital twins. OPC UA supports more than just data transmission through its semantic capabilities; it also contains an information-centric data model that transfers heterogeneous data into unified information, enabling secure data exchange in industrial systems.

Models can apply to various elements of the supply chain as well as for IP components on a chip. Commercial applications must allow for interplay between components. Therefore, standards are needed to avoid disruption and promote scalability. A standards and guidelines for complex modeling systems to represent IP-sensitive components of a chip are needed to protect intellectual property in the virtual supply chain framework. A forward-looking roadmap that elucidates the integration of AI/ML technologies, would propel the next steps forward; defining the abstraction levels to guide implementation and interpretation will be critical in this effort. A robust framework definition will streamline practices across various industries, notably in establishing new fabrication facilities.

2. Digital Twin Taxonomy and Definitions Digital twin concepts have been deployed in several industry types (e.g., automotive, aerospace, nuclear, etc.)10 . However, the lack of reference standards for digital twin terms, architecture, and models has resulted in poor interoperability of digital twin concepts and interconnection of data, models, and services between different enterprises/domains. There is a need for the microelectronics standards community to formulate a comprehensive definition for digital twins that includes a foundational set of functions and modalities to ensure a unified understanding while also providing extensions tailored to diverse application scenarios, security, and trust, while preserving IP.

3. Security (Data Provenance, Traceability, Digital Thread) Establishing the trustworthiness of digital twins communicating in a complex operating system was a central focus. There is a need to improve interoperability and traceability in the manufacturing process and data sharing in digital twin operations. Standards are needed to protect data provenance / security, preserve data integrity, and protect against data compromise. Secure communication protocols that mitigate malicious activities within and between the ecosystems are also needed. In distributed manufacturing environments, ensuring traceability might be challenging. Thus, there is a need to establish a trusted digital thread of origin using ‘Internet of Things’ (IoT) and AI/ML technologies to monitor assets across the electronics and IoT landscape.

4. Testing, Validation, Verification (Reliability Testing, Uncertainty Verification, Benchmark Testing, Methodologies, Creation of New Metrics) Debugging the initial design of a chip prototype and its manufacturing is a critical aspect of design. The implementation of Continuous Integration (CI)/Continuous Deployment (CD) software pipeline management can facilitate the integration of digital twin technology into chip design and manufacturing processes. By applying CI/CD principles to refine chip and system designs, issues identified throughout the manufacturing supply chain can be addressed iteratively, leveraging the insights gained from twinning the system and its components. It is crucial to incorporate comprehensive testing throughout the standard development process, particularly emphasizing the accurate calibration of reliability testing, especially for advanced packaging and chiplets exposed to rigorous conditions such as vibration and heat cycles.

Current data standards for test formats are outdated, and Electronic Design Automation (EDA) procedures lack portability across different vendors. More tools are required to establish portable stimulus standards, such as open container initiatives aimed at enhancing the portability of analytic outputs. However, the adoption of new standards is hindered by the extensive infrastructure built around the old standards by semiconductor manufacturers, resulting in a slow transition process.

5. Existing Standards (Database of Standards, Analysis of Standards, Governance) Some standards already exist that support digital twin operations in semiconductor manufacturing. There was an expressed need to develop a curated list of standards across the sector and related manufacturing sectors to increase community awareness and to avoid duplication of standards development efforts. For example, there exist numerous competing data management standards (from IPC, SEMI, IEC, ISO, and IEEE). Comprehensive review actions are recommended to clarify the extent of standardization and data governance. Data ownership and management are perennial issues in a distributed manufacturing / supply chain system, such as in the semiconductor industry. Standard for data storage duration and clear governance protocols were identified as gaps for both digital twins and the supply chain.

6. Develop Benchmarks and Metrics Models to Specific Use Cases The current practices in utilizing data from semiconductor design, manufacturing, and packaging are generic and not application specific and are not descriptive, predictive, or suitable for decision-making. For example, there are needs for comprehensive wafer defect maps for manufacturing and packaging that could be used to calibrate the synthetic benchmarks generated by the EDA community for design purposes. Similarly, there are needs for benchmarks in thermal imaging hotspot detection11 . Thus, there is a critical need to develop benchmarks and metrics models tailored to specific use cases in the semiconductor industry, particularly in the realms of chip design, manufacturing, packaging, and testing. This requires high-quality datasets to serve as benchmarks, informing various aspects of DT technology by providing a standardized testing methodology, in an industry where data-sharing is limited.

Recommendations

## RECOMMENDATIONS

In addition to the identification of technical standards priorities, several other themes and recommendations emerged during the plenary and breakout session discussions. The recommendations fell into two categories: general standards development, and specific recommendations for chiplets interfaces and digital twin standards activities.

## GENERAL STANDARDS DEVELOPMENT RECOMMENDATIONS

Navigating The Semiconductor Standards Landscape Current existing semiconductor and microelectronics standards collections are distributed across a variety of SSOs / SDOs, making it difficult for users to get reliable answers to questions such as the following:

- What is the best standard for my specific application or need?

- Are there alternatives to the standards I’m using that are a better fit to my application?

- Are there conflicts, interactions, or dependencies with competing standards?

- If I can’t find a relevant standard, does this mean there is a gap and a new standard is needed, or is it that I just haven’t found the right place? SDOs / SSOs would need to be willing to work together to create comprehensive tools for search and discovery across the many standards databases. Such a tool would be valuable for use across the industry, saving time, reducing inefficiencies, and promoting interoperability. A suggested mechanism for creating such a tool could be an “alliance of alliances” to develop an appropriate metadata registry, or its equivalent, powered by AI-enabled analytics. This would also serve to promote broader adoption and use of existing standards and reduce duplication of standards efforts. Collaboration Among SSOs/SDOs In addition to helping with navigating the standards landscape, an alliance of standards setting and development organizations (SSOs/SDOs) is needed to develop the technical standards identified in the workshops. Many of the identified gaps fall into the scope of more than one SDO, thus there is a need for the SDOs to collaborate in creating unified standards that will address the identified gaps. There is an opportunity for standards organizations to work in more collaborative ways to address both rapidly evolving technology needs and increasing interdependencies between sectors and ecosystems. For example, the current overlapping and duplicative standards for traceability and cybersecurity creates inefficiencies and inadvertent conflicts within / between ecosystems and require alignment across stakeholders. Cross-cutting technical standards alignment between segments including designers, supply chains, manufacturers, and beyond are required. Specifically, technical standards for panel form factors, SoC chip design, chiplet interconnection, thermal and power management, connectors, design automation, and more are needed because the inextricable coupling between these otherwise disparate ecosystems.

There is need for a clearly defined scope, value proposition, and operating modalities for the alliance of alliances, since each SSO / SDO represents an alliance among its stakeholders. Examples of roles suggested by participants for a high-level alliance included the following.

- Develop industry-wide standards strategies that optimize benefits across sectors,

- Coordinate efforts among SSOs to promote complementarity and interoperability across standards,

- Combine technical expertise and other capabilities for standards that integrate and interconnect the various segments of the materials, supply, and manufacturing chains,

- Promote awareness of existing standards and ongoing standards development efforts to minimize duplication or conflicting results, and

- Facilitate the development of a standards-capable workforce through partnerships among SSOs, industry, universities, and others. Incentives to Stimulate Collaboration Between SSOs/SDOs A means is needed to incentivize the SSOs/SDOs to work together. The current business models preclude inter- SDO, and in some cases intra-SDO, collaborations. It would take an external impetus to change this reality. A public-private partnership (PPP) collaboration between a government agency and an alliance of SSOs/SDOs could be used to finance and create the needed standards. The PPP could provide support to organizations for standards and interoperability work within these organization’s portfolios that are of mutual interest to industry and CHIPS R&D objectives. Standards Roadmaps There is the need for the development and continued advancement of standards roadmaps in areas such as integration of artificial intelligence and machine learning into digital twin frameworks. Standards roadmaps are inextricably tied to technology roadmaps. The proposed alliance of SDOs should work with semiconductor technology roadmap developers, such as iNEMI, IEEE, IDRS, etc., to coordinate standards development efforts and promote industry progress, including, but not limited to, building broad consensus with open forums and technical workshops to consolidate knowledge, identify areas requiring standardization, and promote advancements in the relevant fields. Adapting Technical Standards from Other Sectors In addition to the challenges and complexities in navigating the semiconductor and microelectronics standards landscape, there is the need to understand and adapt existing digital twin standards that currently exist for other manufacturing sectors. Several industry types (e.g., automotive, aerospace, nuclear, etc.) have successfully implemented digital twin in manufacturing. However, the lack of reference standards for digital twin terms, architecture and models has resulted poor interoperability of digital twin concepts, the interconnection of data, models, and services between different enterprises / domains.

Standards Education There was broad agreement on the need to develop a skilled and diverse workforce as essential to enabling a sustainable domestic semiconductor industry and to achieving the economic and national security goals of the CHIPS and Science Act. Sustained U.S. microelectronics industry competitiveness will require collaboration between businesses, governments, education and training providers, economic and workforce development organizations, unions, community-based organizations, and other supporting entities to help recruit, train, hire, and retain a highly skilled and diverse semiconductor workforce. There is a need for evidence-based learning activities that develop and/or integrate industry standards into the training programs for the entire semiconductor industry workforce. Standards education at all levels is vital for an optimized and secure semiconductor supply chain. It is estimated that the semiconductor industry relies on over 1,000 key standards, without which costs would be much higher for the industry12 . Standards literacy is a prerequisite for effectively leveraging these resources. Broadening Participation in Standards There is a need to enable broad access for small and medium sized entities (SMEs), and university-based research. Suggestions included the need to develop a strong vision for standards development, innovation, community building, and collaboration, and the importance of broadening participation across all levels, from students to experts in industry and academia.

## CHIPLETS INTERFACES AND DIGITAL TWIN RECOMMENDATIONS

Further Standards Identification In-depth, follow-up technical discussions (e.g., through additional workshops, working group activities, etc.) were recommended for each of the top three technical standards gap categories for digital twins in semiconductor manufacturing: data interoperability, digital twin taxonomy and definitions, and security. The discussions are needed to further flesh out the specific standards needs within each category. Existing Standards The need to identify and understand existing standards was identified as one of the top gaps for digital twins. However, there are numerous existing standards in the complex semiconductor standards landscape across a broad range of technical domains. The recommendation to complete a critical assessment of existing standards to avoid duplication or siloing of efforts applies to both chiplet interfaces and digital twins as well as other technology areas. Learning from Digital Twins in Other Sectors There was a recommendation to learn-from and adapt technical standards from other manufacturing sectors into the semiconductor manufacturing ecosystem. Several industry types (e.g., automotive, aerospace, nuclear, etc.) have successfully implemented digital twin in manufacturing. However, the lack of reference standards for

digital twin terms, architecture, and models has resulted in poor interoperability of digital twin concepts, the interconnection of data, models, and services between different enterprises / domains. Chiplets as a Use Case for Digital Twin Chiplets interfaces optimization is recommended as a use case for Digital Twin standards development. Chipletadvanced packaging co-optimization is expected to be critical to the realization of volume production of chiplet technology. Specifically, the test, yield, and reliability of the chiplet technology will rely on AI-assisted, physicsinformed digital twins to diagnose problems based on field measurements, as well as diagnosing and fixing production issues.

Summary and Next Steps

## SUMMARY AND NEXT STEPS

Participants in the standards workshops identified the top standards gaps and recommendations, which together serve as the foundation for community strategies to develop standards needed to advance chiplet and digital twin technologies across the semiconductor sector. Specifically, the strategy for chiplet interface technical standards includes the numerical methods for system optimization; cyber-physical security; general testing and verification; interconnect communication protocols; process design kits (PDKs); and reliability and failure mode analysis standards. For digital twins, the strategy covered priorities including interoperability; digital twin taxonomy and definitions; security; testing, validation, and verification; collating existing standards; and developing benchmarks and metrics models for specific use cases. As part of the strategies, technical experts volunteered to help champion and participate in the development of the needed technical standards. For some of the priorities, the experts will initiate the new work item proposals and lead/serve on existing technical committees within SSOs/SDOs. For other priorities, it was suggested that the standards development could be done in industry-led public-private partnerships, such as an alliance of the existing standards setting and development organizations (SSOs/SDOs), to ensure the coordination necessary to develop robust, cross-cutting technical standards to support the emerging chiplets and digital twin ecosystems. Collectively, these strategies will provide the basis for working together to create a vibrant microelectronics standards ecosystem that is smarter, faster, and more inclusive and agile in enabling innovation.

Appendices

## APPENDIX A: WORKSHOP ORGANIZING COMMITTEE

CHIPS R&D engaged a planning committee comprised of representatives from industry, SSOs and NIST with expertise in the semiconductor and microelectronics industry to design, publicize, and execute the Standards Workshop. The Workshop Organizing Committee met on a biweekly basis in the months leading up to the workshop to plan a highly collaborative event that aligned with the needs and priorities of the semiconductor and microelectronics standards community. Individuals that participated in Workshop Organizing Committee activities included: Adam Cron Synopsys Tom Katsioulas Archon Design Solutions, Inc. Paul Trio SEMI Standards Bapi Vinnakota Lawrence Berkeley National Laboratory Parshuram Zantye Lam Research Simon Frechette NIST Engineering Laboratory Michael Pease NIST Information Technology Laboratory Guodong Shao NIST Engineering Laboratory Yaw Obeng CHIPS R&D Program Jan Obrzut CHIPS R&D Program Mary Bedner CHIPS R&D Program

## APPENDIX B: CHIPLETS INTERFACES WORKSHOP AGENDA

Day 1: December 12, 2023 / 8:30AM - 5:35PM Time Topic Presenter 7:30–8:30 am Check-in 8:30–8:35 am Introduction to the workshop / review agenda / logistics Jan Obrzut (CHIPS R&D) 8:35–8:50 am Keynote 1: Chiplets – The Centerpiece of Advanced Packaging Subramanian Iyer (Director, National Advanced Packaging Manufacturing Program, CHIPS R&D) 8:50–9:05 am Keynote 2: Importance of Technical Standards in the Semiconductor Ecosystem Kathleen Kingscott (IBM Research) 9:05–10:30 am Panel 1: Tutorial on Chiplets Interface Standards Lalitha Immaneni (Intel) Moderator

1. Die-to-die Parallel Interfaces for the Emerging Chiplet Market

2. Building the Open Chiplet Economy

3. A Standard for Chiplet Interconnect Test & Repair

4. Dense Off Chip Integration (DOCI) by Advanced Packaging

1. Elad Alon (Blue Cheeta Analog)

2. Bapi Vinnakota (Open Compute Project)

3. Sreejit Chakravarty (Ampere)

4. Dev Gupta (APSTL) 10:30–10:45 am Break 10:45–11:45 am Breakout Session 1: Discuss and prioritize ideas related to panel 1 Led by SIDEM and Corner Alliance facilitators 11:45–12:00 pm Report Out from Breakout Session 1 Workshop participants and facilitators 12:00–1:15 pm Lunch 1:15–2:15pm Panel 2: State-of-the-art in Chiplets Interfaces Gretchen Greene (NIST) Moderator

Time Topic Presenter

1. Removing the Barriers to Custom Silicon

2. Packaging and Chiplets: Needs for Standards and EDA Evolution

3. Advanced Packaging, Assembly, Test, and Failure Analysis

4. Experience and Ideas for Enhancing the Chiplet Ecosystem, Die-to-die Interfaces, Packaging Supply Chain Limitations, Business Model Challenges, and Optical Packaging Requirements

5. Chiplets Interfaces Challenges in Packaging

1. Andreas Olofsson (Zero ASIC)

2. Lalitha Immaneni (Intel)

3. Yan Li (Samsung)

4. Chen Sun (Ayar Labs)

5. Jeff Rearick (AMD) 2:15–3:15pm Breakout Session 2: Discuss and prioritize ideas related to panel 2 Led by SIDEM and Corner Alliance facilitators 3:15–3:30pm Report Out from Breakout Session 2 Workshop participants and facilitators 3:30pm–4:00pm Break 4:00pm–4:45pm Panel 3: Current State of Research in Chiplets Veruska Malave (NIST) Moderator

1. Photonics Packaging

2. Modeling Challenges of Systems Co-Design

3. High-Level Approaches to Hardware and Embedded Security

4. Opportunities in Chiplets: Bioelectronics and Information-Power Efficiency

1. Peter O’Brien (Tyndall Institute)

2. Ganesh Subbarayan (Purdue University)

3. Ramesh Karri (NYU)

4. Pamela Abshire (U. Md) 4:45–5:15 pm Breakout Session 3: Prioritize ideas from panels 1, panel 2, and panel 3 Led by SIDEM and Corner Alliance facilitators 5:15–5:35pm Report Out from Breakout Session 3 Workshop participants and facilitators 5:35pm Adjourn

Day 2: December 13, 2023 / 8:30AM - 12:30PM Time Topic Presenter 8:30 –9:30 am PANEL 4: Summary Discussion/Takeaways from Day 1 Andreas Olofsson (Zero Asic) Moderator Questions:

- What are the technical standards gaps?

- What information is needed to address the gaps?

- How do we prioritize which standards to work on?

- Who can help with the standards development effort?

- Which SSO's should be working on these issues? Panelists:

1. Bapi Vinnakota (Open Compute Project)

2. Lalitha Immaneni (Intel)

3. Chen Sun (Aylar Labs)

4. Melissa Grupen-Shemansky

## (SEMI)

5. Debendra Das Sharma (UCIe Consortium Standards) 9:30 – 10:30 am Breakout Session 4: Discuss and prioritize ideas related to panel 4 Led by SIDEM and Corner Alliance facilitators 10:30 –11:00 am Break 11:00 –12:00pm Report Out from Breakout Session 4 and consolidation of priorities Workshop participants and facilitators 12:00 –12:30 pm Discuss next steps Jan Obrzut & Yaw Obeng (CHIPS R&D Office) 12:30 pm End of workshop - adjourn

## APPENDIX C: DIGITAL TWIN WORKSHOP AGENDA

Day 1: December 14, 2023 / 8:30AM - 5:35PM Time Topic Presenter 7:30–8:30 am Check-in 8:30–8:40 am Introduction to the workshop / review agenda / logistics Yaw Obeng (CHIPS R&D Office) 8:40–8:50 am Welcome Eric Lin (CHIPS R&D Deputy Director) 8:50–9:05 am Keynote: Leveraging CHIPS Acts Public-private Partnerships to Evolve Standards for Design & Manufacturing Digital Twins Tom Katsioulas (Archon Design Solutions, Inc.) 9:05–10:30 am Panel 1: Tutorial on digital twin standards Carol Handwerker (Purdue University) Moderator

1. Semiconductor Digital Twins: Status and Challenges

2. Intel Automated Factory Solutions

3. International Standard for Digital Twins IPC-2551

4. Digital Twin Data Foundation

1. Mark da Silva (SEMI)

2. Paul Schneider (Intel)

3. Matt Kelly (IPC)

4. Krishan Chawla (LAM Research) 10:30–10:45 am Break 10:45–11:45 am Breakout Session 1: Discuss and prioritize ideas related to panel 1 Led by facilitators 11:45–12:00 pm Report Out from Breakout Session 1 Workshop participants and facilitators 12:00–1:15 pm Lunch 1:15–2:15pm Panel 2: What is the state-of-the art in Digital Twin? Mark da Silva (SEMI) Moderator

Time Topic Presenter

1. Electronics Digital Twin (eDT) for High Quality, Safe and Secure Software: Unlocking Full Potential – Where Standards Might Help

2. Silicon Lifecycle Data Format

3. Artificial Intelligence/Machine Learning (AI/ML) for Digital Twin

4. Secure Data Platform for Digital Twin

5. Standards for Semiconductor Test Digital Twins (Virtual Test)

1. Filip Thoen (Synopsys)

2. Adam Cron (Synopsys)

3. James Moyne (U. Michigan)

4. Dave Huntley (PDF Solutions)

5. Ken Butler (Advantest) 2:15–3:15pm Breakout Session 2: Discuss and prioritize ideas related to panel 2 Led by facilitators 3:15–3:30pm Report Out from Breakout Session 2 Workshop participants and facilitators 3:30pm–4:00pm Break 4:00pm–4:45pm Panel 3: What is the current state of research for digital twins? Adam Cron (Synopsys) Moderator

1. Heterogeneous Integration Roadmap (HIR) Modeling & Simulation Technical Working Group

2. Collaborative and Federated Data Analytics for Connected Systems

3. Feasible Digital Twins for Large Distributed Personalized Manufacturing Systems

4. Digital Twin for Security and Security of Digital Twins

1. Chris Bailey (Arizona State University)

2. Raed Al-Kontar (University of Michigan)

3. Giulia Pedrielli (Arizona State University)

4. Ramesh Karri (NYU) 4:45–5:15 pm Breakout Session 3: Discuss and prioritize ideas from panel 1, panel 2, and panel 3 Led by facilitators 5:15–5:35pm Report Out from Breakout Session 3 Workshop participants and facilitators 5:35pm Adjourn

Day 2: December 15, 2023 / 8:30AM - 12:30PM Time Topic Presenter 8:30–9:30 am Panel 4: Summary Discussion / Takeaways from Day 1 Giulia Pedrielli (Arizona State University) Moderator Questions:

- What are the technical standards gaps?

- What information is needed to address the gaps?

- How do we prioritize which standards to work on?

- Who can help with the standards development effort?

- Which SSO’s should be working on these issues? Panelists:

1. Bapi Vinnakota (Open Compute Project)

2. Matt Kelly (IPC)

3. Mark da Silva (SEMI)

4. Debendra Das Sharma (UCIe Consortium Standards) 9:30–10:30 am Breakout Session 4: Discuss and prioritize ideas related to panel 4 Led by facilitators 10:30–11:00 am Break 11:00–11:15am Report Out from Breakout Session 4 Workshop participants and facilitators 11:15–12:00pm Consolidation and ranking of priorities Yaw Obeng & Jan Obrzut (CHIPS R&D Office) 12:00–12:30 pm Discuss next steps Yaw Obeng & Jan Obrzut (CHIPS R&D Office) 12:30 pm End of workshop – adjourn

## APPENDIX D: WORKSHOP DATA COLLECTION

During both days of each workshop, moderators, technical facilitators, and note-takers collected data from panelists and breakout session participants to capture their ideas and inputs on both the session topics and discussion questions. The goal was to identify key standards priorities that will ensure continued growth of chiplets and digital twin technology in the rapidly evolving semiconductor industry. Given the length of the workshop, the moderators and technical facilitators used multiple knowledge capture methods, including session recordings, meeting minutes, virtual meeting platform chat entries, technical notes, poll responses, and form submissions to ensure all contributions were documented. Reviewing all data sources allowed the report writers to characterize the discussions that took place over the two days of each event and identify key thematic topics.

## APPENDIX E: STANDARDS PRIORITY AREAS FOR CHIPLETS

Ranking Priority Description 1 System optimization (modeling, simulation, and testing standards) Creating benchmarks for system optimization through modeling, simulation, and standardized testing 2 Security and traceability testing standards Establishing protocols for security and traceability to enhance chip integrity 3 General testing and verification standards (outside of security) Developing universal testing and verification benchmarks beyond security aspects 4 Interconnection protocol Defining a standardized interconnection protocol to streamline chip communication 5 Chiplet abstraction (e.g., PDK) Crafting a chiplet abstraction framework such as a Process Design Kit (PDK) 6 Reliability and failure analysis standards Setting standards for reliability assessments and failure analysis procedures 7 Interoperability Ensuring seamless chip interoperability across various systems and platforms 8 Communication protocols Formulating communication protocols to facilitate chiplet interactions 9 Data for EDA optimization Generating data that optimizes Electronic Design Automation (EDA) processes 10 Interface integrity Guaranteeing interface integrity for consistent chiplet connectivity 11 Mechanical/dimensional form factors Standardizing mechanical and dimensional form factors for chiplet integration 12 Common performance specifications Creating common performance specifications to unify chiplet expectations 13 Conformity and compliance Establishing conformity and compliance benchmarks for industry-wide adherence

Ranking Priority Description 14 Standards workforce development (e.g., awareness, understanding, and compliance of current standards) Fostering a workforce knowledgeable in standards development, awareness, and compliance 15 Chiplet specification Defining chiplet specifications to guide design and integration 16 Thermal modeling and specification Developing thermal modeling and specifications to manage chiplet heat dissipation 17 Maintenance and repair standards Outlining maintenance and repair standards to ensure chiplet longevity 18 Location/positioning of the interface Standardizing the location and positioning of interfaces for uniformity 19 Digital thread for the component (die, package design kits) Creating a digital thread for components to trace die and package design 20 Governance Setting up governance structures to oversee chiplet standardization efforts

## APPENDIX F: STANDARDS PRIORITY AREAS FOR DIGITAL TWINS

Ranking Priority Description 1 Interoperability (Data models, DT interfaces, DTs communicating with other DTs) Standards that enable appropriate data sharing across the digital twin ecosystem while both preserving the security and integrity of the data and protecting intellectual property rights 2 Digital twin taxonomy and definition Establish a comprehensive digital twin definition and foundational taxonomy for the semiconductor standards community 3 Security (Data provenance, traceability, digital thread) Develop standards and protocols to establish the trustworthiness of digital twins communicating in a complex operating system 4 Testing, validation, and verification (Reliability testing, uncertainty verification, benchmarks testing, methodologies, creation of new metrics) Develop and incorporate comprehensive testing throughout the standard development process, particularly emphasizing the accurate calibration of reliability testing, 5 Existing standards (Database of standards, analysis of standards, governance) Need to assemble an interactive, parameterized list of standards and standards for data management and ownership 6 Develop benchmarks and metrics models to specific use cases Tailored semiconductor benchmarks for design, manufacturing, packaging, and testing are needed to clarify descriptive, predictive, or decision-making model purposes 7 Electronic Design Automation (EDA) simulations/simulator Standards for EDA simulations, especially for chip design, manufacturing, packaging, and testing 8 Synchronization Standards for data sharing between factory systems at rates aligned with DT requirements to mirror physical operations in real-time 9 Accessibility (Including educational/ workforce development standards) Create standardized educational and training frameworks to increase accessibility and to ensure that the workforce is adequately equipped to leverage the full potential of digital twin.

## ENDNOTES

1 “United States Government National Standards Strategy for Critical and Emerging Technology” (2023), https://www.whitehouse.gov/wp-content/uploads/2023/05/US-Gov-National-Standards-Strategy-2023.pdf 2 “Summary Report: CHIPS R&D Program Standards Summit” (2024), https://doi.org/10.6028/NIST.CHIPS.1400-1 3 P.L. 117-167, CHIPS and Science Act of 2022 (Creating Helpful Incentives to Produce Semiconductors) 4 “Incentives, Infrastructure, and Research and Development Needs to Support a Strong Domestic Semiconductor Industry: Summary of Responses to Request for Information” (2022), NIST Special Publication (SP) NIST SP 1282, https://doi.org/10.6028/

## NIST.SP.1282

5 DOC CHIPS activities were authorized by Title XCIX—Creating Helpful Incentives to Produce Semiconductors for America of the William M. (Mac) Thornberry National Defense Authorization Act for Fiscal Year 2021 (Pub. L. 116-283, often referred to as the CHIPS Act). 6 D. Fox, J.M. Monsalve Diaz, X. Li, “Chiplets and the Codelet Model” (2022), https://doi.org/10.48550/arXiv.2209.06083 7 A. Limaye et al., "Towards Automated Generation of Chiplet-Based Systems Invited Paper" (2024), 2024 29th Asia and South Pacific Design Automation Conference (ASP-DAC), Incheon, Korea, Republic of, pp. 771-776, doi: 10.1109/ASP- DAC58780.2024.10473980 8 K. Wang et al. “A review of the technology standards for enabling digital twin [version 2; peer review: 2 approved]” (2022), Digital Twin, 2:4, https://doi.org/10.12688/digitaltwin.17549.2 9 OPC Unified Architecture Specification. Document OPCUS 10000-1, (2015-2022), https://reference.opcfoundation.org/v105/ Core/docs/Part1/ 10 IOT Analytics, “How the world’s 250 Digital Twins compare? Same, same but different” (2022), https://iot-analytics.com/howthe-worlds-250-digital-twins-compare/ 11 S.S. Salvi and A. Jain, “Detection of Unusual Thermal Activities in a Semiconductor Chip Using Backside Infrared Thermal Imaging” (2021), ASME, Journal of Electronic Packaging, 143(2):020901, https://doi.org/10.1115/1.4049291 12 G. Tassey, "Competing in Advanced Manufacturing: The Need for Improved Growth Models and Policies" (2014), Journal of Economic Perspectives, 28 (1): 27-48, http://dx.doi.org/10.1257/jep.28.1.27
