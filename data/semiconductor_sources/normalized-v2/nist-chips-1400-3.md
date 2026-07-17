---
candidate_id: nist-chips-1400-3
title: CHIPS Research and Development Office's Standards Workshops Summary Report
domains:
- materials_equipment
- wafer_fabrication
- packaging_testing
source_name: National Institute of Standards and Technology
source_url: https://doi.org/10.6028/NIST.CHIPS.1400-3
document_type: government_report
published_at: '2024-01-01'
document_version: NIST.CHIPS.1400-3
authority_level: official
claim_type: government_report
doi: 10.6028/NIST.CHIPS.1400-3
license_name: NIST Technical Series public-use terms
license_url: https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications
retrieved_at: '2026-07-15T09:34:01+00:00'
content_hash: 53535dddc8959a778b4a92e5abe32963aa5d2c33b0d9630877db2665bba3e0a8
is_synthetic: false
---

# CHIPS Research and Development Office's Standards Workshops Summary Report

## SUMMARY REPORT

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards Workshop April 2–3, 2024 CHIPS R&D Digital Twin Data Interoperability Standards Workshop April 4–5, 2024

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops ii CHIPS for America includes the CHIPS Program Office, responsible for semiconductor incentives, and the CHIPS Research and Development Office, responsible for R&D programs. NIST promotes U.S. innovation and industrial competitiveness by advancing measurement science, standards, and technology in ways that enhance economic security and improve our quality of life. NIST is uniquely positioned to successfully administer the CHIPS for America program because of the bureau’s strong relationships with U.S. industries, its deep understanding of the semiconductor ecosystem, and its reputation as fair and trusted. Visit https://www.chips.gov to learn more.

## DISCLAIMER STATEMENT

Certain commercial entities, equipment, or materials may be identified in this document in order to describe an experimental procedure or concept adequately. Such identification does not imply recommendation or endorsement by the National Institute of Standards and Technology, the U.S. Department of Commerce, or any part of the United States Government, nor is it intended to imply that the entities, materials, or equipment are necessarily the best available for the purpose

## COPYRIGHT

This document is a work of the U.S. Government and is not subject to copyright in the United States (see 17 U.S.C. § 105). Foreign rights reserved. All tables and figures in this report, unless otherwise noted, were produced by NIST and DOC employees.

## NIST CHIPS 1400-3

https://doi.org/10.6028/NIST.CHIPS.1400-3

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops iii

## TABLE OF CONTENTS

Appendix B: CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards Workshop

Executive Summary & Introduction

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 1

## EXECUTIVE SUMMARY

The CHIPS and Science Act appropriated $50 billion to the Department of Commerce’s CHIPS for America program both to support semiconductor research and development (R&D) and to expand semiconductor manufacturing capacity in the United States. Within CHIPS for America, the mission of the National Institute of Standards and Technology’s (NIST) CHIPS Research and Development Office (CHIPS R&D) is to accelerate the development and commercial deployment of foundational semiconductor technologies by establishing, connecting, and providing access to domestic research efforts, tools, resources, workers, and facilities. A key element in achieving these CHIPS R&D goals is to accelerate the private sector-led development and deployment by industry of effective technical standards. CHIPS R&D has developed a comprehensive standards roadmap that aligns with the needs of private sector semiconductor standards efforts, the requirements of CHIPS legislation, and the provisions of the U.S. Government National Standards Strategy for Critical and Emerging Technologies (USG NSS CET)1 . The CHIPS R&D standards roadmap is centered on a vision for a vibrant microelectronics standards ecosystem that is smarter, faster, and more inclusive and agile in enabling innovation. CHIPS R&D has undertaken a series of events to solicit the global semiconductor industry’s perspectives on, and input into aligning the government effort with the industry’s technical standards needs. The first of these CHIPS R&D standards activities was a Standards Summit event held in September 2023, in Washington, D.C., which brought together private sector thought leaders to identify strategic technical standards priorities for the semiconductor sector. Five major technical strategic standards priorities emerged from that Summit2 , including:

- Chiplets

- Digital Twins

- Data Interoperability

- Supply Chain Security and Resilience

- Advanced Packaging and Heterogeneous Integration In December 2023, two follow-on CHIPS R&D Technical Standards Workshops were organized with the goal of identifying specific standards needs within the first two of the priority areas identified in the Summit: Chiplets and Digital Twins3 . In April 2024, two CHIPS R&D workshops focused on data standards needs for Supply Chain Security and Digital Twin Interoperability were held, as a follow-on to recommendations from both the Summit and the first two workshops. The April workshops were organized as hybrid events at the NIST National Cybersecurity Center of Excellence (NCCoE) in Rockville, Maryland. A planning committee comprising representatives from industry and NIST organized the workshops, which brought together over 250 technical experts for each session to identify community data standards priorities and action plans. Most participants were from the semiconductor industry, but there was also strong participation from academia, standards setting / development organizations (SSOs / SDOs), small and medium sized companies, industry alliances, and government entities. The workshops featured a mix of panel and keynote presentations from renowned experts in the field, followed by breakout discussions that identified the technical gaps and standards opportunities; over 120 standards ideas

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 2 were submitted by participants in response to our discussion prompts. These ideas were discussed, consolidated, and upvoted to define the top five priorities. The rankings of the top standards priorities from the respective workshops are as follows: Supply Chain Trust and Assurance Data Standards Priorities:

1. Develop semantic definitions, assets, and standards to support traceability and provenance of semiconductor materials and data, both in the physical and virtual space, across the entire product lifecycle.

2. Develop an updated, more accessible, parameterized database of existing supply chain trust and assurance data standards (e.g., taxonomy, matrix, graph, analytic tool, etc.).

3. Define more precise and scalable methods and identifiers for traceability to enable more credible provenance.

4. Develop an umbrella/macro-level framework for aligning standardization activities across the semiconductor supply chain.

5. Establish a standardized format, architecture, security measures, automated key management, proof of authority, and identity verification and management for sustainment chains and distributed ledgers within the semiconductor supply chain. Digital Twin Data Interoperability Standards Priorities:

1. Develop a shared hierarchical relationship of digital twin systems (mesh/context and layers of detail/ granularity/resolution).

2. Develop a standard method for quantifying and communicating uncertainty between the real event (i.e., actual metrology) and the predictions from the digital twin (i.e., virtual metrology).

3. Develop a clear definition and metrics for context-specific interfaces.

4. Identify needs for global, automated, cryptographic identifiers and key management infrastructure (to ensure seamless, zero trust cybersecurity for digital twins across domains).

5. Identify the needs for standard(s) for tracing/attributing changes to data as it travels through the supply chain. In addition, workshop participants made broad recommendations for the semiconductor standards communities. Some of the key recommendations are listed below. These do not necessarily fall under any one of the specific priority standards identified above.

- Information, not Data, Sharing: Companies and stakeholders need to exchange information, but the format for exchange has to be robust enough to protect their data. In an effort to protect intellectual property (IP) and other sensitive data, while sharing information along the supply chain, new standards are needed- not just standards for interoperability, but interoperable standards.

- Standards Roadmap: The standards community should develop a roadmap that forecasts new data

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 3 interoperability standards required to support improved operations and scaling, and how standards must evolve to support the expanded use of DT systems in the future.

- Standards Registry: There is a need for a centralized registry for standardized semantic assets to better enable searching for the relevant standards to use for a particular application.

- Cryptographic Identifier Needs: Participants suggested examining existing cybersecurity initiatives that could provide a valuable starting point for creating standards on global, automated cryptographic identifiers and zero-trust.

- Collaboration in Standards Development: Starting with a common framework that outlines essential data elements and tracing methodologies, next steps should focus on collaboration and incremental development of standards to advance standardization in data tracing and attribution. This report also provides additional information about the two workshops, including more-detailed descriptions of the identified standards, priority areas, and recommendations that emerged from the discussions.

## INTRODUCTION CHIPS FOR AMERICA

The CHIPS and Science Act4 appropriated $50 billion to the Department of Commerce’s CHIPS for America program, both, to support semiconductor research and development (R&D) and to expand semiconductor manufacturing capacity in the United States. This includes $39 billion for the Department of Commerce (the Department) to expand domestic semiconductor manufacturing capacity through the incentives program and $11 billion to advance U.S. leadership in semiconductor R&D. R&D advances will be realized through four programs: the National Semiconductor Technology Center (NSTC), the National Advanced Packaging Manufacturing Program (NAPMP), the CHIPS Metrology Program, and the Semiconductor Manufacturing and Advanced Research with Twins (SMART) USA Institute. These investments, across both the R&D and incentives programs, seek to strengthen U.S. competitiveness, support domestic manufacturing and innovation, and create good jobs across the country.

## CHIPS R&D MISSION AND GOALS

Within CHIPS for America, the mission of the National Institute of Standards and Technology’s (NIST) CHIPS Research and Development Office (CHIPS R&D) is to accelerate the development and commercial deployment of foundational semiconductor technologies by establishing, connecting, and providing access to domestic research efforts, tools, resources, workers, and facilities. CHIPS R&D aims to achieve the following goals by 2030:

- U.S. Technology Leadership: The United States establishes the capacity to invent, develop, prototype, manufacture, and deploy the foundational semiconductor technologies of the future.

- Accelerated Ideas to Market: The best ideas achieve commercial scale as quickly and cost effectively as possible.

- Robust Semiconductor Workforce: Inventors, designers, researchers, developers, engineers, technicians, and staff meet evolving domestic government and commercial sector needs.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 4 A key to achieving these CHIPS R&D goals is to accelerate the private sector-led development and deployment of effective pertinent technical standards.

## BACKGROUND FOR CHIPS R&D STANDARDS EFFORT

CHIPS R&D has developed a comprehensive standards roadmap in response to calls from the private sector for semiconductor standards efforts, the requirements of CHIPS legislation, and the provisions of the United States Government National Standards Strategy for Critical and Emerging Technologies (USG NSS CET)1 , as summarized below:

- Standards were identified by private sector stakeholders as a core competency for CHIPS R&D. Both the need for standards and ensuring that standards align across different stakeholders were highlighted in many of the responses to NIST’s request for information to guide the design of CHIPS programs5 .

- The CHIPS Act6 provision (15 USC §4656 (e)) copied below, specifies that private-sector-led technical standards for the semiconductor industry should be an integral part of the CHIPS R&D strategy: “the Director of the National Institute of Standards and Technology shall carry out a microelectronics research program to enable advances and breakthroughs in measurement science, standards, material characterization, instrumentation, testing, and manufacturing capabilities that will accelerate the underlying research and development for metrology of next generation microelectronics and ensure the competitiveness and leadership of the United States within this sector” (emphasis added).

- The CHIPS and Science Act (42 USC §18951(a)) specifies guiding principles for standards, which include: (1) openness, transparency, due process, balance of interests, appeals, and consensus in the development of international standards are critical; (2) voluntary consensus standards, developed through an industry-led process, serve as the cornerstone of the United States standardization system and have become the basis of a sound national economy and the key to global market access; (3) strengthening the unique United States public-private partnerships approach to standards development is critical to United States economic competitiveness; and (4) the United States Government should ensure cooperation and coordination across Federal agencies to partner with and support private sector stakeholders to continue to shape international dialogues in regard to standards development for emerging technologies.

- The United States Government National Standards Strategy for Critical and Emerging Technologies

## (USG NSS CET)1

has four major objectives for CETs, including semiconductors and microelectronics: investment, participation, workforce, and integrity and inclusivity.

## CHIPS R&D

Standards Roadmap

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 6

## CHIPS R&D STANDARDS ROADMAP VISION

The vision of the CHIPS R&D Standards Roadmap2 is for: A vibrant microelectronics standards ecosystem that is smarter, faster, and more inclusive and agile in enabling innovation. This vision provides for working with the semiconductor standards sector in enhancing strategic focus, matching the pace of standards development to the pace of innovation in the semiconductor sector, expanding opportunities for participation in standards activities, and responding effectively to the needs of industry.

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

- Standards at the speed of innovation,

- A standards-enabled global market,

- Standards as innovation platforms,

- Inclusive standards leadership,

- Education for career opportunities in standards development, and

- A diverse standards-capable workforce. In pursuing these outcomes, the CHIPS R&D standards effort is intended to:

- enhance U.S. economic security through standards that support innovation, collaboration, and a vibrant domestic landscape of small, medium, and large corporations;

- support national security through standards that underpin a domestic semiconductor industry that is resilient, reliable, secure, and a global leader in semiconductor technologies; and

- enable future innovation through standards that provide for interoperability, set out powerful measurement capabilities, and establish effective testing and assurance methods that spur adoption of new technologies.

## CHIPS R&D

Workshops: Introduction and Overview

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 8

## CHIPS R&D WORKSHOPS: INTRODUCTION AND OVERVIEW

Achieving CHIPS R&D’s goals will require cooperation and collaboration across the private sector standards setting organizations serving the semiconductor standards landscape. As such, CHIPS R&D has undertaken a series of activities, including but not limited to open workshops, to solicit the global semiconductor industry’s perspectives on, and input into, aligning the government effort with the industry’s technical standards needs. The first of these CHIPS R&D standards activities was a Standards Summit event held in September 2023, in Washington, D.C., which brought together private sector thought leaders to identify strategic technical standards priorities for the semiconductor sector. During the Summit, there was significant discussion about the expanding roles of chiplets and digital twins (DTs) as emerging technology enablers in the semiconductor industry, among other topics2 . The Summit was followed by two, one-and-a-half-day hybrid technical standards workshops that were held in December 2023 and brought together technical experts to identify community priorities for chiplets interfaces and DT technical standards3 . As follow-on to the December 2023 workshops, the CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards and CHIPS R&D Digital Twin Data Interoperability Standards Workshops were held in April 2024. These workshops were held as hybrid events at the NIST National Cybersecurity Center of Excellence (NCCoE) in Rockville, Maryland and focused on data standards needs for supply chain security and DT interoperability. Most of the participants were from the semiconductor industry (approximately 60%); the workshop also attracted strong support and participation from academia, standards setting organizations, industry alliances, and government. These workshops were planned by an organizing committee comprising leaders from standards setting organizations (SSOs), industry, and government representatives (see Appendix A). The workshops featured a mix of panel and keynote presentations from renowned experts in the field, followed by breakout discussions that identified the technical gaps and standards opportunities (see the workshop agendas in Appendix B and Appendix C). The invited keynote speakers and panelists provided insights and identified key challenges in each of the topic areas to stimulate conversations in the subsequent breakout sessions. During the moderated breakout sessions, the workshop participants reflected on the speaker insights, discussed the questions provided by the planning committee, and identified gaps and technical standards opportunities. The approach used to capture input from participants to inform this report is described in Appendix D. For each workshop, over 120 standards ideas were submitted by participants in response to our discussion prompts. Ideas were discussed and consolidated and upvoted to define the top 5 priorities for each workshop.

## CHIPS R&D

Semiconductor Supply Chain Trust and Assurance Data Standards Workshop

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 10

## CHIPS R&D SEMICONDUCTOR SUPPLY CHAIN TRUST AND ASSURANCE DATA STANDARDS WORKSHOP

The CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards Workshop was focused on the role of technical standards for information sharing within the semiconductor and microelectronics industry supply chain. The workshop also brought together technical experts from industry, academia, standards setting organizations, and industry alliances to identify community priorities for specific standards efforts, identify the technical standards that the semiconductor industry community should prioritize, and outline plans to work on these priorities. The specific goals and outcomes for the workshop included:

- Gaining insight into the data and information needs in the field of supply chain integrity within the semiconductor and electronics industry from industry leaders, standard organizations, and experts.

- Identifying priorities for data sharing standards, as well as efforts in semiconductors and microelectronics to securely and effectively share pertinent information within the supply chain.

- Engaging the semiconductor and microelectronics community and building a network of stakeholders for supply chain integrity within the electronics industry.

- Providing input to standards and measurement programs supporting the needs of the semiconductor industry. The workshop featured plenary, panel, and interactive breakout sessions. Participants collaborated and discussed key questions and topics that will shape future data standards activities. The workshop agenda is provided in Appendix B. The design of the workshop centered on the overall goal of identifying industry technical standards priorities for secure and effective data / information sharing within the supply chain, and was organized around the following themes:

1. Defining the landscape, scope, and focus of electronics supply chain digital security standardization efforts.

2. Identifying and overcoming hurdles — What are the challenges that need to be addressed through standardization?

3. Building the future What are the standards solutions for supply chain?

4. Providing standards opportunities and priorities for developing a community action plan. The fourth topic area led to the final breakout sessions of the workshop in which open discussions and polling techniques were used to refine the list of industry’s top priorities for semiconductor supply chain trust and assurance data standards. The collective participant feedback was used to generate a rank-ordered list of standards areas to pursue. The top five priority areas identified by participants are described in the next section.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 11

## STANDARDS PRIORITIES FOR SUPPLY CHAIN TRUST AND ASSURANCE DATA STANDARDS

The top five priorities identified by the workshop participants, in ranked order, included:

- Develop semantic definitions, assets, and standards to support traceability and provenance of semiconductor materials and data, both in the physical and virtual space, across the entire product lifecycle.

- Develop an updated, more accessible, parameterized database of existing supply chain trust and assurance data standards (e.g., taxonomy, matrix, graph, analytic tool, etc.).

- Define more precise and scalable methods and identifiers for traceability to enable more credible provenance.

- Develop an umbrella/macro-level framework for aligning standardization activities across the semiconductor supply chain.

- Establish a standardized format, architecture, security measures, automated key management, proof of authority, and identity verification and management for sustainment chains and distributed ledgers within the semiconductor supply chain.

1. Develop semantic definitions, assets, and standards to support traceability and provenance of semiconductor materials and data, both in the physical and virtual space, across the entire product lifecycle. Establishing taxonomy, including semantic definitions, assets, and standards, is needed to facilitate traceability, provenance, and information sharing across the entire semiconductor product lifecycle, encompassing both physical and virtual realms. This involves delineating coherent terminology, information/data models, and protocols to track the origin, history, and transformation of semiconductor materials and associated data from production to end use. The data governance frameworks are vital for traceability and provenance. Thus, the semantic standards need to comprehend specific application contexts, such as unique identifiers, blockchain, and distributed ledger technology. Standardizing terminology across the industry is crucial to cultivating a collective understanding of the microelectronics supply chain and its trajectory, thereby ensuring the security and reliability of semiconductors and their components. A collaborative approach to establishing a standardized vocabulary is essential for fostering a shared understanding and worldview that can effectively identify and mitigate common sources of risk. Artificial intelligence (AI)/machine learning (ML), and graph analytics of accumulated data could facilitate the creation of semantic assets and enhance comprehension across multiple levels of abstraction. Protocols that share and exchange information can be used to build knowledge networks, which can leverage AI/ML technologies. Common data models offer technical solutions for interoperability, simplified data management, and application by applying structural and semantic consistency across multiple applications and deployment domains. This would provide an opportunity to significantly impact the industry, including creating points of entry for small and medium-sized companies into the supply chain.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 12

2. Develop an updated, more accessible, parameterized database of existing supply chain trust and assurance data standards (e.g., taxonomy, matrix, graph, analytic tool, etc.). Creating a structured, searchable taxonomy of existing supply chain trust and assurance standards would significantly benefit stakeholders by streamlining access to relevant standards. Currently, these standards are dispersed across various SSOs and trade group domains, lacking integration and cohesion. Consolidating and prioritizing these standards for different stakeholders into a unified, searchable database would provide immense value, particularly within the semiconductor industry. This proposed database would employ structured parameters, such as taxonomy and analytic tools, to organize and present the standards in a user-friendly, holistic, and context-aware format. This approach would enable efficient access and navigation, fostering greater transparency, collaboration, and trust across the semiconductor supply chain. By serving as a centralized repository, the database would standardize trust and assurance guidelines and best practices across the industry. Proposed Enhancements and Tools include:

- Mapping Tool for Standards Application: A visual mapping tool could be developed to identify and display applicable standards throughout various stages of the semiconductor supply chain. This would provide stakeholders with clear insights into which standards apply to specific locations or processes within the supply chain.

- Standards Review and Updates: Many existing standards are outdated and fail to address current industry needs. Conducting a comprehensive review and updating these standards is critical. Furthermore, there is a pressing need for “living standards” that dynamically evolve alongside technological advancements. Protocols should also be established for phasing out obsolete standards.

- Pilot Initiative and Analytics Integration: As a pilot, a standards matrix for selecting priority areas could be developed. Utilizing advanced tools such as graph analytics or AI-enabled capabilities, relationships between supply chain standards could be mapped and analyzed. These insights could be used to draft and align new standards with specific tools or processes, ensuring practical applicability and adherence.

- Stakeholder Education: A persistent challenge lies in educating stakeholders on how to locate, interpret, and implement standards. This gap is particularly pronounced for small businesses and startups, where users may struggle to identify the most critical standards. A robust training program, integrated with the database, could address this issue by empowering stakeholders to effectively engage with standards. A centralized, interactive database of supply chain trust and assurance standards, complemented by mapping and analytic tools, would strengthen the semiconductor supply chain. By consolidating standards, facilitating stakeholder education, and enabling ongoing evolution, the industry can achieve greater alignment, transparency, and resilience in the face of rapidly changing technologies and global demands.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 13

3. Define more precise and scalable methods and identifiers for traceability to enable more credible provenance. Counterfeits account for approximately half of all known malicious attacks on the semiconductor supply chain, highlighting the need for robust traceability standards. Implementing a transparent cyber-physical identity ecosystem, compatible with digital systems and network protocols, is critical for ensuring provenance and mitigating counterfeits. Key Recommendations:

- Provenance Certificates: Establish standardized certificates that detail information such as manufacturer, fabrication location, and source of input materials can help validate provenance. These certificates must include mechanisms for independent verification by end-users for critical systems.

- Scalable Identity Metrics: Develop precise and diverse metrics to ensure end-to-end traceability across legacy and modern systems, with scalable solutions to support national security requirements.

- Cybersecurity for Cryptographic Artifacts: Protect cryptographic artifacts linked to provenance data, ensuring the integrity of verification mechanisms to prevent fraudulent certifications.

- Provenance Validation: Strengthen assurance mechanisms by integrating user-verifiable data, enabling stakeholders to confirm component authenticity and reliability. Actionable Steps:

- Map existing industry traceability standards, such as SEMI T23 (from semi.org) and IPC 1782 (from IPC. org), to identify gaps and align with proposed solutions.

- Enhance NIST's National Cybersecurity Center of Excellence’s (NCCoE) supply chain traceability efforts to create a linked ledger system for provenance.

- Validate existing systems while exploring forward-looking improvements for ease of traceability and quality management.

- Pursue SBIR/STTR projects to advance alignment on traceability and provenance standards. By addressing these gaps, the semiconductor supply chain can achieve greater transparency, reliability, and security, fostering trust in high-assurance environments.

4. Develop an umbrella/macro-level framework for aligning standardization activities across the semiconductor supply chain. The semiconductor industry currently suffers from fragmented efforts to develop and implement trust data and assurance standards. By creating a macro-level framework that aligns existing efforts and integrates innovative practices, the semiconductor industry can address its unique challenges and establish a more resilient, transparent, and efficient supply chain ecosystem. A unified, macro-level framework is needed to harmonize these disparate initiatives, providing a cohesive structure that fosters collaboration and consistency throughout the supply chain. Such a framework would enhance transparency, efficiency, and reliability in operations, while optimizing costs and resources by improving understanding and navigation of existing standards rather than creating entirely new ones.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 14 Key Components of the Framework:

- Integration and Harmonization of Existing Standards:

- Identify, map, and align existing standards to improve interoperability and reduce redundancy.

- Leverage established frameworks to ensure compatibility across global stakeholders and regulatory environments.

- Tailored Data Governance and Security Protocols:

- Develop semiconductor-specific governance models to manage data integrity, security, and accessibility.

- Implement selective disclosure mechanisms for controlled access to sensitive information.

- Traceability Through Legal Identifiers:

- Use standardized legal identifiers to establish reliable traceability mechanisms for components and materials across the supply chain.

- Technology-Driven Optimization:

- Employ advanced digital tools, such as value mapping and DT modeling, to streamline standardization and enhance supply chain visibility.

- Support scalability and adaptability to accommodate evolving technologies and market demands.

- Rigorous Testing and Validation:

- Design robust testing protocols to verify compliance with standards, ensuring quality, authenticity, and reliability of components. Challenges and Mitigation Strategies: Implementing such a comprehensive framework across the variety of global supply chains presents several challenges, including but not limited to:

- Breadth of Stakeholders: Address varying regional, operational, and regulatory requirements by developing flexible and adaptable protocols.

- Adoption and Scalability: Facilitate phased adoption with targeted outreach, training, and capacitybuilding initiatives.

- Compliance and Enforcement: Establish clear, enforceable compliance mechanisms to ensure widespread adherence to the framework

5. Establish a standardized format, architecture, security measures, automated key management, proof of authority, and identity verification and management for sustainment chains and distributed ledgers within the semiconductor supply chain. To enhance trust, security, and efficiency within the semiconductor supply chain, a standardized framework must be established for data formats, system architectures, security protocols, automated key management, proof of authority, and identity verification. These measures will ensure the integrity, security, and reliability of transactions and data across distributed ledger systems while enabling interoperability and scalability.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 15 Core Objectives of the Framework:

- Standardized Data Formats and Architectures:

- Define consistent data structures and system designs to facilitate seamless interoperability between various technologies and stakeholders.

- Ensure backward compatibility with legacy systems to accommodate existing infrastructure.

- Enhanced Security Measures:

- Implement automated key management to simplify secure cryptographic operations and reduce manual errors.

- Establish robust identity verification protocols to safeguard against unauthorized access.

- Adopt proof-of-authority mechanisms to strengthen authentication and ensure legitimate participation in the ledger.

- Data Integrity and Traceability:

- Develop standardized schema compliance to verify data accuracy and ensure provenance.

- Explore alternative validation methods to improve flexibility while maintaining traceability. Challenges and Mitigation Strategies: Despite its advantages, implementing such a framework comes with several challenges, including:

- Stakeholder Consensus: Achieving agreement on standard formats and architectures among diverse participants with varying technological and operational needs.

- Mitigation: Foster collaboration through cross-industry working groups, workshops, and consensusbuilding initiatives.

- Security vs. Complexity: Balancing advanced security measures with usability and manageability.

- Mitigation: Leverage automation to streamline security implementations, reducing the burden on stakeholders.

- Legacy System Integration: Ensuring compatibility between new standards and existing systems.

- Mitigation: Design flexible protocols and transition plans to support gradual adoption without disrupting operations.

- Privacy Concerns: Addressing data privacy issues related to stringent identity verification and data management practices.

- Mitigation: Use selective disclosure and privacy-preserving technologies to ensure compliance with privacy standards. Initial Focus Areas:

- Interoperability through Standardization: Define universal data formats and system architectures to create a cohesive supply chain network.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 16

- Robust Security Protocols: Specify methods for automated key management, proof of authority, and identity verification to enhance system resilience.

- Traceability and Integrity Mechanisms: Establish a standardized schema and explore novel validation techniques to ensure product provenance and accuracy. Workshop Conclusions By addressing these challenges and prioritizing these focus areas, the semiconductor industry can build a sustainable and secure framework for distributed ledger technologies. This approach will promote trust, transparency, and resilience within the supply chain while enabling scalability and adaptability in a rapidly evolving technological landscape. Collaboration among industry leaders, regulatory bodies, and technology providers will be critical to achieving consensus and ensuring successful implementation.

## CHIPS R&D

Digital Twin Data Interoperability Standards Workshop

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 18

## CHIPS R&D DIGITAL TWIN DATA INTEROPERABILITY STANDARDS WORKSHOP

“A digital twin is a set of virtual information constructs that mimics the structure, context, and behavior of a natural, engineered, or social system (or system-of-systems); is dynamically updated with data from its physical twin; has a predictive capability; and informs decisions that realize value. The bidirectional interaction between the virtual and the physical is central to the digital twin7 .” At its core, a DT enables operations research by optimizing all available resources to maximize success. The ultimate goal of the DT is to reduce the uncertainty, error, and randomness in decision making8 . DTs in manufacturing enable proactive decision-making, predictive maintenance, scenario testing, and collaboration among stakeholders. Participants discussed the potential for DT technologies to drive progress in the semiconductor and microelectronics industry, and the role of data interoperability standards for DTs in the semiconductor manufacturing ecosystem. In an effort to streamline the discussions, the workshop focused on standards needs for a specific use case: the application of a DT for manufacturing in the chiplet-packaging module. The CHIPS R&D Digital Twin Data Interoperability Standards Workshop was focused on the role of technical standards for information sharing to enable interoperable DTs within the semiconductor and microelectronics industry. The workshop also brought together technical experts from industry, academia, standards setting organizations, and industry alliances to identify community priorities for specific standards efforts, identify the technical standards the semiconductor industry community should prioritize, and outline plans to work on these priorities. The specific goals and outcomes for the workshop included:

- Gaining insight into the data and information needs for adapting and utilizing DT technology within the semiconductor and electronics industry.

- Identifying priorities for data sharing standards, as well as efforts in semiconductors and microelectronics to securely and effectively share pertinent information within the various workflows, such as design, integration, and manufacturing.

- Engaging the semiconductor and microelectronics community and building a network of stakeholders for the application of DTs within the electronics industry.

- Providing data requirement input to standards and measurement programs supporting the needs of the semiconductor industry. The workshop featured plenary, panel, and interactive breakout sessions. Participants collaborated and discussed key questions and topics that will shape future data interoperability technical standards activities. The workshop agenda is provided in Appendix C. The design of the workshop centered on the overall goal of identifying industry technical standards priorities for secure and effective data / information sharing within the supply chain to enable interoperable DTs, and specifically for chiplet integration and manufacturing. The workshop was organized around the following themes:

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 19

1. Defining the landscape, scope, and focus of digital twins in the semiconductor ecosystem. A clear definition of digital twin was a key topic, as that was needed to level-set the discussions.

2. Identifying and Overcoming Hurdles — What are the challenges to digital twin interoperability that need to be addressed through standardization?

3. Building the future — What are the standards solutions for digital twin interoperability?

4. Developing standards opportunities and priorities for developing a community action plan. The fourth topic area led to the final breakout sessions of the workshop in which open discussions and polling techniques were used to refine the list of industry’s top priorities for DT interoperability technical standards. The collective participant feedback was used to generate a rank-ordered list of the top priority chiplet interface standards areas to pursue.

## STANDARDS PRIORITIES FOR DIGITAL TWIN DATA INTEROPERABILITY

The top five priorities identified by the workshop participants, in ranked order, included:

- Develop a shared hierarchical relationship of digital twin systems and a roadmap for standards using smart manufacturing principles.

- Develop a standard method for communicating the accuracy and uncertainty between the real event (i.e., actual metrology) and the predictions from the digital twin (i.e., virtual metrology).

- Develop a clear definition and metrics for context-specific interfaces.

- Identify needs for global, automated, cryptographic identifiers and key management infrastructure (to ensure seamless, zero trust cybersecurity for digital twins across domains).

- Identify the needs for standard(s) for tracing/attributing changes to data as it travels through the supply chain.

1. Develop a shared hierarchical relationship of digital twin systems and a roadmap for standards using smart manufacturing principles The need for a structured hierarchical relationship between DT systems within the semiconductor supply chain was identified as a foundational framework for high-fidelity digital models of manufacturing resources and processes. Such a comprehensive hierarchical framework requires clearly defined DT types, their context specific applications, and the relationships between DT systems that support key functions across the semiconductor ecosystem. It will entail the physical interactions and fusing of data from both the virtual and physical worlds. The proposed hierarchy will represent the various stages of semiconductor manufacturing workflows, e.g., chip design, fabrication, testing, validation, packaging, assembly, and test. These functions include, but are not limited to, predictive maintenance, run-to-run process control, data augmentation, virtual metrology, and yield / reliability prediction. By aligning DT systems within a hierarchical structure, stakeholders can better describe and standardize data requirements and identify existing standards that are applicable to each DT application.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 20 Challenges and Mitigation Strategies: Despite its advantages, implementing such a framework comes with several challenges, including:

- Describing requirements specific to different categories of DT applications and defining relationships between DT systems.

- Developing a DT standards roadmap, which will be hampered by challenges including overcoming development silos, where DTs are built using non-standardized reference models, algorithms, and interfaces, leading to interoperability and data sharing challenges.

- Governance and management of unclean factory (i.e., fab) data, which includes erroneous data obtained using varying life cycles of data models and data granularity between systems, and securely sharing data while protecting intellectual property (IP)9 .

- Mitigation: This challenge, however, provides opportunities for deploying “in-fab” data augmentation and virtual metrology strategies.

2. Develop a standard method for communicating the accuracy and uncertainty between the real event (i.e., actual metrology) and the predictions from the digital twin (i.e., virtual metrology) Context-specific DTs are often developed with varying levels of fidelity and produce different outputs based on application. The usefulness of such DT systems depends on how accurately the digital model predicts the target real-life events8 . Thus, the need for standards to communicate the qualitative accuracy and output of a DT to allow stakeholders to make informed decisions was identified. Such a standard would prioritize capturing trends and qualitative correctness, such as time saved, particularly in the contexts of workforce development and algorithm testing. Challenges and Mitigation Strategies:

- Unrestricted sharing of DT outputs without divulging IP could limit the interoperability of the DT ecosystem.

- Mitigation: Share information rather than data. The concept of creating digital “cousins” was posed as a solution to address the relative accuracy of a DT. These “cousins” would offer lower fidelity compared to DTs but still manage to communicate context-specific information, instead of discrete data, for decision making. Meanwhile, higher fidelity DTs would be reserved as paid services to protect IP. This strategy would enhance trust and visibility by allowing users to access information about a DT, its originator, and its qualitative accuracy. Furthermore, participants recommended the development of a standardized data format to facilitate communication and increase interoperability.

- Creating a standard for accurately communicating data between DTs presents numerous challenges, particularly regarding the protection of IP and the adaptation to new technologies and interfaces. In a global ecosystem, each twin contains data from various business units, which complicates standardization efforts. Moreover, extending DTs across multiple organizations further amplifies the necessity for IP protection7 .

- Mitigation: New methods for capturing qualitative accuracy effectively are needed to enhance traceability and allow for the assessment of the quality and reputation of a DT and its originator.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 21

- Existing methods for capturing qualitative accuracy between DT and real event have limitations.

- Mitigation: New methods for assessing the quality of the DT output relative to the physical event are needed. Existing verification, validation, and uncertainty quantification (VVUQ) standards, such as ASME PTC 19.1 or SEMI E133, can be the basis for crafting a DT accuracy and uncertainty standard. This will require a study of the verification process to identify additional gaps that could inform the standard.

3. Develop a clear definition and metrics for context-specific interfaces. A standard set of methods, frameworks, or technical specifications for semiconductor context-specific interfaces should be developed to enhance communication interoperability and improve the operating efficiency and performance of DT systems. Designing DT application interfaces specific to each application's context, purpose, or objectives ensures that standards are specifically tailored to meet the diverse and complex needs of various domains. Clearly defined context and objectives for interfaces, including the intersections between machines, DT systems, and/or processes in the supply chain, would help guide the development of DT standards. Preferred definitions should be specific enough to describe individual interface applications without becoming overly granular and describing ontologies. Suggestions included a layered approach to defining context-specific interfaces, using the Open Systems Interconnections (OSI) model, or adopting a tiered approach with an Interface A (interface to tool) and B (application-to-application interface) using SEMI’s Interface B Model as a starting point. Challenges and Mitigation Strategies:

- Defining context-specific interfaces presents several challenges, particularly regarding semantic interfaces and common security protocols. While mechanical interfaces are established for physical connections, defining semantic interfaces proves more challenging. These interfaces demand a deeper comprehension of the context and meaning of the data being exchanged, which can vary widely between applications. Furthermore, ensuring interfaces adhere to a universal security model across the supply chain complicates a tiered or layered approach to developing standardized definitions for data exchange architecture, formats, and communications protocols specific to DT application contexts.

- Mitigation: It was suggested that the industry should first gain a better understanding of how data flows through the supply chain before creating the definitions; without this understanding, it would be difficult to identify all interfaces present in the supply chain and effectively produce standard contextdependent interfaces for exchanging data across DT technologies. Additionally, the industry must first reach agreements on system and data requirements for the context-specific interfaces before defining them.

4. Identify needs for global, automated, cryptographic identifiers and key management infrastructure (to ensure seamless, zero trust cybersecurity for digital twins across domains) A standardized security protocol that protects intellectual proprietary, and other sensitive data that must be exchanged across DT layered tiers, was identified as a need. The establishment of such a standard with global, automated cryptographic identifiers and key management would not only enhance traceability but also enable secure communication among DTs.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 22 Implementing zero-trust security can pose several challenges, including:

- Zero-day vulnerabilities can be exposed during initial DT system deployment. Unwinding legacy hardware and software can create unexpected security lapses and may require major architectural, hardware, and software changes to be successful10 .

- Security robust enough to be considered zero-trust can often hinder communication between systems and slow down operations during implementation. Finding a balance between security and visibility can also prove limiting.

5. Identify the need for standard(s) for tracing/attributing changes to data as it travels through the supply chain. This standards area involves setting protocols and formats guiding how data that support DT technology components and process steps are recorded, traced, updated, accessed, and communicated throughout the supply chain. This is necessary to ensure that all stakeholders, from equipment manufacturers to end users, can reliably track the origins and transformations of data, which is vital for attesting to verifiable data integrity for DT-supported systems. For instance, if a DT model predicts a wafer defect in a simulated fabrication process, stakeholders should be able to trace back through the data to understand the prediction's basis, verifying the data's accuracy and the model's assumptions. Workshop Conclusions By addressing these challenges and prioritizing these focus areas, the semiconductor industry can build a sustainable and secure framework for data interoperability in DTs. This approach will promote trust, transparency, and resilience within the DT ecosystem while enabling scalability and adaptability in a rapidly evolving technological landscape. Collaboration among industry leaders, regulatory bodies, and technology providers will be critical to achieving consensus and ensuring successful implementation.

Recommendations

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 24

## RECOMMENDATIONS

In addition to the standards priorities, several other industry-wide recommendations emerged during the workshop. These do not necessarily fall under any one of the specific priority standards identified earlier in this report.

## INFORMATION, NOT DATA, SHARING

Data is IP and must be protected. Therefore, the data must be converted into sharable information. Companies and stakeholders need to exchange information, but the format for exchange has to be standardized and robust enough to protect their data.

## STANDARDS ROADMAP

The standards community recommended developing a roadmap that would forecast what new data interoperability standards are required to support improved operations and scaling of DT systems today and how standards must evolve to support the expanded use of DT systems in the future. Consider a roadmap for standards (possibly using the IEEE® IRDS™ smart manufacturing section as a starting point).

## STANDARDS REGISTRY

Participants recommended creating a centralized database for standardized semantic assets to better enable searching for the relevant standards to use for a particular application. They suggested an audit of existing applicable standards, as well as a market audit of the industry.

## CRYPTOGRAPHIC IDENTIFIER NEEDS

Participants suggested examining existing SEMI cybersecurity initiatives, which, while focused on malware, could provide a valuable starting point for creating a standard on global, automated cryptographic identifiers. They also suggested creating tokenization standards to augment a zero-trust standard.

## COLLABORATION IN STANDARDS DEVELOPMENT

Participants recommended next steps that focus on collaboration and incremental development of standards to advance standardization in data tracing and attribution. The initial efforts should concentrate on developing a common framework that outlines essential data elements and tracing methodologies. This framework could be based on existing models from successful standards in related areas, such as those developed by SEMI (e.g. SEMI E30 for equipment data acquisition). Leveraging existing data management frameworks could provide a foundation for building more comprehensive standards. Participants also proposed the creation of collaborative pilot projects within the industry to test the practical application of proposed data traceability and attribution standards on a smaller scale before wider implementation. These projects would help identify potential interoperability or security gaps and standards areas that could use further refinement.

Summary and Next Steps

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 26

## SUMMARY AND NEXT STEPS

Overall, the path forward involves a balanced approach that combines documentary standard development with practical testing and verifying refinement, ensuring that the standards developed are both robust and adaptable to the fast-evolving technology landscape of semiconductor manufacturing. Collaborative efforts among stakeholders, including working groups and consortia, are essential to identifying these challenges and opportunities for specific information flow and data standards development. Additionally, participants noted the need to characterize the maturity of DT technologies used for different functions across the semiconductor supply chain as high, medium, or low to inform the prioritization of standards development activities. They also called on the standards community to develop new validation methodologies to ensure the accuracy and reliability of DT models, addressing challenges related to time, cost, and maintenance. Organizations like SEMI and the International Roadmap for Devices and Systems (IRDS) can serve as valuable platforms for publicizing these new standards, roadmaps, and best practices.

Appendices

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 28

## APPENDIX A: WORKSHOP ORGANIZING COMMITTEE

CHIPS R&D engaged a planning committee comprised of representatives from academia, industry, SSOs, and NIST with expertise in the semiconductor and microelectronics industry to design, publicize, and execute the Standards Workshop. The workshop organizing committee met on a biweekly basis in the months leading up to the workshop to plan a highly collaborative event that aligned with the needs and priorities of the semiconductor and microelectronics standards community. Individuals that participated in workshop organizing committee activities included: SSOs Paul Trio SEMI Standards Matt Kelley IPC

## TECHNICAL EXPERTS

Dave Huntley PDF Solutions Harvey Reed The MITRE Corporation James Moyne University of Michigan Chris Bailey Arizona State University Jon Boyens NIST Information Technology Laboratory Gretchen Greene NIST Material Measurement Laboratory Michael Pease NIST Information Technology Laboratory

## NIST CHIPS R&D OFFICE

Yaw Obeng NIST CHIPS R&D Office Jan Obrzut NIST CHIPS R&D Office Mary Bedner NIST CHIPS R&D Office

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 29

## APPENDIX B: CHIPS R&D SEMICONDUCTOR SUPPLY CHAIN TRUST AND ASSURANCE DATA STANDARDS WORKSHOP AGENDA

Day 1: April 2, 2024 / 8:30AM - 5:30PM ET Time Topic Presenter 7:30–8:30 am Check-In 8:30–8:50 am Introduction (Review logistics / agenda / workshop objectives) Yaw Obeng or Jan Obrzut (CHIPS R&D Office) 8:50–9:05 am Keynote: DARPA’s History in Semiconductor Supply Chain Trust and Assurance Standards Carl McCants (DARPA) 9:05–9:15 am CHIPS Manufacturing USA Introduction Eric Forsythe (CHIPS R&D) 9:15–10:30 am Panel 1: Define the landscape, scope, and focus of electronics supply chain digital security standardization efforts

1. Gretchen Greene (NIST)

2. Chris Ritter (Idaho National Lab)

3. Christophe Bégué (PDF Solutions) (Virtual) 10:30–10:45 am Networking Break 10:45–11:45 am Breakout Session 1 Led by facilitators 11:45–12:00 pm Report Out from Breakout Session 1 Facilitators with workshop participants 12:00–1:15 pm Lunch 1:15–2:15 pm Panel 2: Overcoming Hurdles - What are the challenges that need to be addressed through standardization?

1. Rosa Javadi (Jabil)

2. Eric Simmon (NIST, ITL)

3. Jennifer Lynn (IBM/SEMI Cybersecurity Consortium) 2:15–3:15 pm Breakout Session 2 Led by facilitators 3:15–3:30 pm Report Out from Breakout Session 2 Facilitators with workshop participants 3:30–3:45 pm Networking Break

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 30 Time Topic Presenter 3:45–4:30 pm Panel 3: Building the future – What are the standards solutions for supply chain?

1. Harvey Reed (MITRE)

2. Bettina Weiss (SEMI) (Virtual)

3. Carlos Aguayo Gonzalez (PFP Cybersecurity)

4. Ted Prescop (Multibeam Corporation) (Virtual) 4:30–5:00 pm Breakout Session 3 Led by facilitators 5:00–5:15 pm Report Out from Breakout Session 3 Facilitators with workshop participants 5:15–5:30 pm Day 1 Summary of Initial Priorities Led by facilitators 5:30 pm Adjourn Day 2: April 3, 2024 / 8:30AM - 12:30PM ET Time Topic Presenter 8:30–8:40 am Welcome/CHIPS R&D Introduction Richard-Duane Chambers 8:40–9:30 am Panel 4: Summary discussion/takeaways from Day 1 Panelists:

1. Jennifer Lynn (IBM/SEMI Cybersecurity Consortium)

2. Dan Gamota (Jabil)

3. Harvey Reed (MITRE) 9:30–9:50 am Networking Break 9:50–10:30 am Breakout Session 4: Discuss standards opportunities and priorities for developing a community action plan Led by facilitators 10:30–11:30am Consolidation and Discussion of Priorities Facilitators with workshop participants 11:30–11:45 am Networking Break 11:45–12:30 pm Ranking of Priorities and Discussion of Next Steps: Drafting initial recommendations for supply chain trust and assurance data standards roadmap Facilitators with Yaw Obeng & Jan Obrzut (CHIPS R&D) 12:30 pm End of Workshop - Adjourn

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 31

## APPENDIX C: CHIPS R&D DIGITAL TWIN DATA INTEROPERABILITY STANDARDS WORKSHOP AGENDA

Day 1: April 4, 2024 / 8:30AM - 5:30PM ET Time Topic Presenter 7:30–8:30 am Check-In 8:30–8:50 am Introduction (Review logistics / agenda / workshop objectives) Yaw Obeng and Jan Obrzut

## (CHIPS R&D)

8:50–9:05 am CHIPS Manufacturing USA Introduction Eric Forsythe (CHIPS R&D) 9:05–10:45 am Panel 1: Define the landscape, scope, and focus of digital twins in semiconductor manufacturing standardization efforts

1. Kemaljeet Ghotra (PDF Solutions)

2. James Moyne (U. Michigan)

3. Ben Davaji (Northeastern U.) (Virtual)

4. Serge Leef (Microsoft)

5. Gurtej Sandhu (Micron)

6. Victor Zhirnov (SRC) 10:45–11:00 am Networking Break 11:00–11:55 am Breakout Session 1 Led by facilitators 12:00–12:05 pm Report Out from Breakout Session 1 Facilitators with workshop participants 12:05–1:15 pm Lunch 1:15–2:15 pm Panel 2: Define the communication and data exchange challenges that need to be addressed through standardization

1. Gretchen Greene (NIST)

2. Alan Weber (PDF/Cimetrix) (Virtual)

3. Larry Pileggi (CMU) 2:15–3:15 pm Breakout Session 2 Led by facilitators 3:15–3:30 pm Report Out from Breakout Session 2 Facilitators with workshop participants 3:30–3:45 pm Networking Break

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 32 Time Topic Presenter 3:45–4:30 pm Panel 3: Define the governance and security challenges that need to be addressed through standardization

1. Guodong Shao (NIST)

2. James Moyne (U. Michigan)

3. Sameer Kher (ANSYS)

4. Mike Pease (NIST)

5. Mike Coner (Blockcity/ASTM) (Virtual) 4:30–5:00 pm Breakout Session 3 Led by facilitators 5:00–5:15 pm Report Out from Breakout Session 3 Facilitators with workshop participants 5:15–5:30 pm Day 1 Summary of Initial Priorities Led by facilitators 5:30 pm Adjourn Day 2: April 5, 2024 / 8:30AM - 12:30PM ET Time Topic Presenter 8:30–8:40 am CHIPS Manufacturing USA Perspective Robert Rudnitsky (Manufacturing USA) 8:40–9:30 am Panel 4: Summary discussion/takeaways from Day 1 1. Melissa Grupen-Shemansky

## (SEMI)

2. Mike Pease (NIST)

3. Dave Henshall (SRC) 9:30–10:15 am Breakout Session 4: Discuss standards opportunities and priorities for developing a community action plan Led by facilitators 10:15–10:30 am Networking Break 10:30–11:30 am Consolidation and Discussion of Priorities Facilitators with workshop participants 11:30–11:45 am Networking Break 11:45–12:30 pm Ranking of Priorities and Discussion of Next Steps: Drafting initial recommendations for digital twin date interoperability standards roadmap Facilitators with Yaw Obeng & Jan Obrzut (CHIPS R&D Office) 12:30 pm End of Workshop - Adjourn

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 33

## APPENDIX D: WORKSHOP DATA COLLECTION

During both days of each workshop, moderators, technical facilitators, and note-takers collected data from panelists and breakout session participants to capture their ideas and inputs on both the session topics and discussion questions. The goal was to identify and prioritize the key data standards needed to enable interoperability in the rapidly evolving semiconductor industry. Given the length of the workshop, the moderators and technical facilitators used multiple knowledge capture methods, including session recordings, meeting minutes, virtual meeting platform chat entries, technical notes, poll responses, and form submissions to ensure all contributions were documented. Reviewing all data sources allowed the report writers to characterize the discussions that took place over the two days of each event and identify key thematic topics. The priorities from the stakeholders covered a broad range of scopes; some were very technically specific, and others were broader recommendations for the semiconductor standards landscape. Where the priorities were specific, the workshop identified the challenges and mitigation strategies for addressing them.

CHIPS R&D Semiconductor Supply Chain Trust and Assurance Data Standards & Digital Twin Data Interoperability Standards Workshops 34

## ENDNOTES

1 “United States Government National Standards Strategy for Critical and Emerging Technology” (2023), https://bidenwhitehouse. archives.gov/wp-content/uploads/2023/05/US-Gov-National-Standards-Strategy-2023.pdf 2 “Summary Report: CHIPS R&D Program Standards Summit” (2024), https://doi.org/10.6028/NIST.CHIPS.1400-1 3 “Summary Report: CHIPS R&D Chiplets Interfaces & Digital Twin Technical Standards Workshops” (2024), https://doi. org/10.6028/NIST.CHIPS.1400-2 4 P.L. 117-167, CHIPS and Science Act of 2022 (Creating Helpful Incentives to Produce Semiconductors) 5 “Incentives, Infrastructure, and Research and Development Needs to Support a Strong Domestic Semiconductor Industry: Sum¬mary of Responses to Request for Information” (2022), NIST Special Publication (SP) NIST SP 1282, https://doi. org/10.6028/NIST.SP.1282. 6 DOC CHIPS activities were authorized by Title XCIX—Creating Helpful Incentives to Produce Semiconductors for America of the William M. (Mac) Thornberry National Defense Authorization Act for Fiscal Year 2021 (Pub. L. 116-283, often referred to as the CHIPS Act). 7 “Foundational Research Gaps and Future Directions for Digital Twins” (2024), National Academies of Sciences, Engineering, and Medicine, The National Academies Press: Washington, DC, https://doi.org/10.17226/26894. 8

## A. Torres, “Fab Insights: A Digital Twin for Semiconductor Manufacturing” (2023), https://srcmapt.org/wp-content/up-

loads/2024/05/SRC_2024_Digital_Twin_Andres_Torres_Public.pdf, (accessed 2/17/2025). 9 “Digital Twins in Semicondcutor Manufacturing” (2024), White Paper based on SEMI Smart Manufacturing Initiative and Semiconductor DT Workshop, SEMI Dec.4-5th, SEMI HQ Milpitas CA. https://discover.semi.org/rs/320-QBB-055/images/SEMI_SM_ Digital_Twins_Whitepaper_FINAL_032924.pdf?version=0 10 “Zero Trust for Hardware Supply Chains: Challenges in Application of Zero Trust Principles to Hardware” (2021), White Paper of the National Defense Industrial Association, Electronics Division, zerotrustwhitepaper_20oct-revc.pdf.
