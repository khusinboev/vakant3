# ============================================================
# src/data/translations/law_articles_en.py
# English translations of the labour-law articles.
# ============================================================

TRANSLATIONS: dict[str, dict[str, str]] = {
    "worktime-norm": {
        "title": "Daily and weekly working time norms",
        "summary": (
            "Under the normal regime — 40 hours per week, 8 hours per day. "
            "Reduced norms are set for certain categories."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 116–117</b>\n\n"
            "<b>Normal working time:</b>\n"
            "Weekly working time must not exceed <b>40 hours</b>. Under a 5-day working week, the daily norm is <b>8 hours</b>; under a 6-day working week, it is <b>7 hours</b> (5 hours on Saturday).\n\n"
            "<b>Reduced working time (Article 116):</b>\n"
            "• Persons under 16 — <b>24 hours/week</b>\n"
            "• Persons aged 16–18 — <b>36 hours/week</b>\n"
            "• Group I and II persons with disabilities — <b>36 hours/week</b>\n"
            "• Employees working in harmful or hazardous conditions — <b>36 hours/week</b>\n\n"
            "<b>Part-time work:</b>\n"
            "By agreement between the employer and the employee, a part-time day or part-time week schedule may be established. In this case, wages are paid for the time actually worked.\n\n"
            "<b>Important:</b> Under reduced working time, wages are paid as for full working time (for persons with disabilities and minors)."
        ),
        "source_label": "Labour Code, Articles 116–117",
    },
    "overtime": {
        "title": "Overtime work and its payment",
        "summary": (
            "Must not exceed 2 hours per day and 120 hours per year. Overtime "
            "hours are paid at 1.5–2 times the regular rate."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 120–121, 157</b>\n\n"
            "<b>Limits on overtime work:</b>\n"
            "• Must not exceed <b>2 hours per day</b> for each employee\n"
            "• Must not exceed <b>120 hours per year</b>\n"
            "• Overtime work on two consecutive days is prohibited\n\n"
            "<b>Who may not be required to work overtime:</b>\n"
            "• Persons under 18\n"
            "• Pregnant women\n"
            "• Mothers raising a child under three years of age\n"
            "• Group I and II persons with disabilities (unless medically cleared)\n\n"
            "<b>Payment procedure (Article 157):</b>\n"
            "• Work on rest days or public holidays — pay at <b>double</b> the rate\n"
            "• The first <b>2 hours</b> after regular working time — at least <b>1.5 times</b> the rate\n"
            "• Subsequent hours — at least <b>2 times</b> the rate\n\n"
            "<b>Important:</b> Instead of overtime pay, an employee may request rest on other days (an additional day off)."
        ),
        "source_label": "Labour Code, Articles 120–121, 157",
    },
    "annual-leave": {
        "title": "Annual leave: duration and payment procedure",
        "summary": (
            "The basic leave is at least 15 working days. For certain categories "
            "(teachers, medical workers, persons with disabilities), extended "
            "leave of up to 18–30 working days applies."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 134–136</b>\n\n"
            "<b>Duration of basic leave:</b>\n"
            "The annual basic leave for all employees is at least <b>15 working days</b>. At most enterprises, the employment or collective agreement sets it at 18–21 working days.\n\n"
            "<b>Extended basic leave (Article 135):</b>\n"
            "• Teaching staff — <b>30 working days</b>\n"
            "• Medical workers — <b>18–30 working days</b> (depending on specialty)\n"
            "• Group I and II persons with disabilities — <b>30 working days</b>\n"
            "• Minors (under 18) — <b>30 working days</b>\n\n"
            "<b>Additional leave:</b>\n"
            "• Harmful or hazardous working conditions — <b>at least 6 additional days</b>\n"
            "• Multi-shift work — a special procedure applies\n"
            "• For long service — under the collective agreement\n\n"
            "<b>Leave pay:</b>\n"
            "Leave pay is calculated based on average daily earnings and must be paid in full <b>no later than 3 days before the start of leave</b>.\n\n"
            "<b>Important:</b> Replacing leave with monetary compensation is allowed <b>only upon dismissal</b>. Replacing leave with money while still employed is against the law."
        ),
        "source_label": "Labour Code, Articles 134–136",
    },
    "sick-leave": {
        "title": "Sick leave certificate: payment procedure and amount",
        "summary": (
            "Sick leave payments range from 60% to 100% depending on length of "
            "service. Paid by the social insurance fund."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 280–281, and the Law «On State Social Insurance»</b>\n\n"
            "<b>Who pays:</b>\n"
            "Sick leave benefits are paid from the <b>state social insurance fund</b>, not by the employer. The employer covers the difference only when internal regulations provide for it.\n\n"
            "<b>Payment percentage (depending on length of service):</b>\n"
            "• Service <b>under 5 years</b> — <b>60%</b> of average earnings\n"
            "• <b>From 5 to 8 years</b> — <b>80%</b>\n"
            "• <b>8 years and more</b> — <b>100%</b>\n\n"
            "<b>Cases of 100% payment regardless of service:</b>\n"
            "• Work injury or occupational disease\n"
            "• Parents raising 3 or more children\n"
            "• Group I and II persons with disabilities\n"
            "• Persons who served in the military (with a veteran's certificate)\n\n"
            "<b>Time limits:</b>\n"
            "• Ordinary illness: <b>up to 30 days</b> (extended if necessary)\n"
            "• Inpatient treatment: without limit\n\n"
            "<b>Important:</b> The sick leave certificate must be submitted to the employer within <b>6 months</b> of receiving it."
        ),
        "source_label": "Labour Code, Articles 280–281",
    },
    "labor-contract": {
        "title": "Concluding an employment contract: mandatory terms",
        "summary": (
            "An employment contract must be concluded in writing. Mandatory "
            "terms: place of work, position, salary amount, working hours."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 74–77</b>\n\n"
            "<b>Form of the contract:</b>\n"
            "An employment contract is concluded in <b>writing</b>. An oral agreement has no legal force. The contract is signed in two copies: one is kept by the employee, the other by the employer.\n\n"
            "<b>Mandatory terms (Article 76):</b>\n"
            "1. Place of work (name and address of the organization)\n"
            "2. The employee's position or occupation\n"
            "3. The date employment begins\n"
            "4. The amount of wages and the payment schedule\n"
            "5. The working time and rest schedule\n"
            "6. Social insurance terms\n\n"
            "<b>Contract term:</b>\n"
            "• <b>Indefinite-term</b> — the main type (preferable)\n"
            "• <b>Fixed-term</b> — maximum <b>5 years</b>; concluded only on grounds specified by law (e.g., seasonal work, a project)\n\n"
            "<b>Probationary period:</b>\n"
            "The contract may specify a probationary period — maximum <b>3 months</b> (<b>6 months</b> for managerial positions).\n\n"
            "<b>Important:</b> If an employee has actually started working but the contract has not been signed, this is grounds for <b>administrative liability of the employer</b>. The employee's rights remain protected regardless."
        ),
        "source_label": "Labour Code, Articles 74–77",
    },
    "probation": {
        "title": "Probationary period: rules and limitations",
        "summary": (
            "The probationary period is usually 3 months, and 6 months for "
            "managers. It is not set for minors, pregnant women, and certain "
            "other categories."
        ),
        "full_text": (
            "📋 <b>Labour Code, Article 84</b>\n\n"
            "<b>Limits of the probationary period:</b>\n"
            "• For ordinary employees — <b>up to 3 months</b>\n"
            "• For managerial positions (director, chief accountant, branch head) — <b>up to 6 months</b>\n"
            "• Seasonal work (under 6 months) — <b>no more than 2 weeks</b>\n\n"
            "<b>The probationary period is not set (Article 84, part 2):</b>\n"
            "• Persons under 18\n"
            "• Pregnant women and mothers with children under 3\n"
            "• Persons hired through a competitive selection process\n"
            "• Persons transferred from another organization\n"
            "• Graduates of educational institutions — for their first job\n"
            "• Persons with disabilities (with a medical indication)\n\n"
            "<b>Employee rights during the probationary period:</b>\n"
            "During the probationary period, the employee enjoys full protection under labour law. Wages, leave, sick pay — all apply on the usual basis.\n\n"
            "<b>If the probation is deemed unsuccessful:</b>\n"
            "The employer must give <b>3 days' written notice</b>. The employee may <b>challenge this decision in court</b>."
        ),
        "source_label": "Labour Code, Article 84",
    },
    "dismissal": {
        "title": "Dismissal: grounds and procedure",
        "summary": (
            "When resigning voluntarily, an employee gives 2 weeks' notice. "
            "Dismissal by the employer requires strict procedure and lawful "
            "grounds."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 100–104</b>\n\n"
            "<b>Employee resignation of their own free will:</b>\n"
            "An employee may terminate the contract at any time by submitting a <b>written notice 14 days in advance</b>. By agreement, the employer may shorten this period.\n\n"
            "<b>Grounds for dismissal by the employer (Article 100):</b>\n"
            "• Liquidation of the organization or staff reduction\n"
            "• Employee's unsuitability for the position held (confirmed by performance appraisal)\n"
            "• Breach of labour discipline (following a prior warning)\n"
            "• Absenteeism (without valid reason, more than 3 hours)\n"
            "• Appearing at work in a state of intoxication\n"
            "• Disclosure of confidential information\n\n"
            "<b>Notice period (for staff reduction):</b>\n"
            "Written notice must be given at least <b>2 months</b> in advance, and another job must be offered.\n\n"
            "<b>Who cannot be dismissed:</b>\n"
            "• <b>Pregnant women</b> — cannot be dismissed on any grounds\n"
            "• <b>Mothers with children under 3</b> — cannot be dismissed due to staff reduction\n"
            "• <b>Employees on leave</b> — cannot be dismissed while on leave\n"
            "• <b>Employees on sick leave</b> — cannot be dismissed during illness\n\n"
            "<b>Important:</b> An unlawfully dismissed employee may, within <b>1 month</b>, apply to court and demand <b>reinstatement and payment of wages for the period of forced absence</b>."
        ),
        "source_label": "Labour Code, Articles 100–104",
    },
    "min-wage": {
        "title": "Minimum wage (MROT) and its effect",
        "summary": (
            "In Uzbekistan, the minimum wage (MROT) is set by a Government "
            "resolution and is increased annually. For 2025, the MROT is "
            "980,000 UZS/month."
        ),
        "full_text": (
            "📋 <b>Labour Code, Article 153, and Government resolutions</b>\n\n"
            "<b>Current situation (2025):</b>\n"
            "By resolution of the Cabinet of Ministers of the Republic of Uzbekistan, the minimum wage (MROT) has been set at <b>980,000 UZS/month</b>.\n\n"
            "<b>Where the MROT applies:</b>\n"
            "• No employee may receive wages below the MROT (at a full rate)\n"
            "• Paying wages below the MROT is an <b>administrative offense</b>\n"
            "• Used as the base indicator when calculating benefits and compensation\n\n"
            "<b>Practical information:</b>\n"
            "• The MROT is only a minimum threshold. The employer may pay any higher amount\n"
            "• The collective agreement may set a minimum wage higher than the MROT\n"
            "• Those working half-time are paid half of the MROT\n\n"
            "<b>Tax benefits:</b>\n"
            "The base calculation value (BCV) is 10% of the MROT and is used when calculating income tax deductions.\n\n"
            "<b>Important:</b> The MROT is reviewed every year. For the latest official value, check the stat.uz or lex.uz websites."
        ),
        "source_label": "Labour Code, Article 153",
    },
    "maternity": {
        "title": "Rights of pregnant women and young mothers",
        "summary": (
            "Pregnant women cannot be dismissed and are not required to work "
            "night shifts. Maternity leave is 132 days. The job is retained "
            "during childcare leave until the child turns 3."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 225–228</b>\n\n"
            "<b>Protection (Article 225):</b>\n"
            "• <b>Dismissal on any grounds is prohibited</b> for a woman whose pregnancy is known\n"
            "• They cannot be required to work at night (22:00–06:00)\n"
            "• Overtime work, business trips, hazardous work — only with written consent\n\n"
            "<b>Maternity leave (Article 227):</b>\n"
            "• Normal delivery — <b>70 days before + 70 days after = 140 days</b>\n"
            "• Complicated delivery — <b>70 days before + 86 days after = 156 days</b>\n"
            "• Multiple birth (twins, etc.) — <b>84 days before + 110 days after = 194 days</b>\n"
            "• Maternity benefit — <b>100%</b> of average earnings\n\n"
            "<b>Childcare leave (Article 228):</b>\n"
            "• Leave may be taken by choice until the child turns <b>3</b>\n"
            "• During this time, <b>the job and position are retained</b>\n"
            "• Counted toward length of service\n"
            "• Benefit — based on the minimum wage (paid from the social insurance fund)\n\n"
            "<b>Important:</b> Childcare leave may also be taken by the father (or another relative). It is not exclusively the mother's right."
        ),
        "source_label": "Labour Code, Articles 225–228",
    },
    "wage-delay": {
        "title": "Employee rights in case of wage delay",
        "summary": (
            "Wages must be paid at least twice a month. For delays, the "
            "employer pays a penalty and is subject to administrative "
            "liability."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 164–166</b>\n\n"
            "<b>Payment schedule (Article 164):</b>\n"
            "Wages must be paid <b>at least twice a month</b>. The exact dates are specified in the employment or collective agreement. If a payment date falls on a rest day or public holiday, it is moved to an earlier date.\n\n"
            "<b>Penalty for delay:</b>\n"
            "For each day of delay, a penalty of <b>1/300</b> of the Central Bank of Uzbekistan's refinancing rate is paid.\n\n"
            "<b>Employee's actions:</b>\n"
            "1. Written request to the employer\n"
            "2. Complaint to the labour inspectorate (at the workplace or the territorial one)\n"
            "3. Appeal to the prosecutor's office\n"
            "4. A lawsuit in court (within the 3-year statute of limitations)\n\n"
            "<b>Employer's liability:</b>\n"
            "• Administrative: a fine of 5 to 20 BCV\n"
            "• Deliberate delay of more than 3 months — <b>criminal liability</b> (imprisonment for up to 3 years)\n\n"
            "<b>Important:</b> The employer has no right to pay wages in goods or services instead of cash — this is against the law."
        ),
        "source_label": "Labour Code, Articles 164–166",
    },
    "holidays": {
        "title": "Rest days and public holidays",
        "summary": (
            "Weekly rest: Saturday and Sunday. 9 official public holidays. "
            "Work on a holiday is compensated with double pay or an additional "
            "day off."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 146–149</b>\n\n"
            "<b>Weekly rest (Article 146):</b>\n"
            "Under a 5-day working week — <b>Saturday and Sunday</b>. Under a 6-day week — <b>Sunday</b>. The employer may change the rest day (for example, at industrial enterprises), but not without the employee's consent.\n\n"
            "<b>Official public holidays in Uzbekistan:</b>\n"
            "• January 1–2 — New Year\n"
            "• March 8 — International Women's Day\n"
            "• March 21–23 — Navruz holiday\n"
            "• May 9 — Day of Memory and Honours\n"
            "• September 1 — Independence Day\n"
            "• October 1 — Teachers' and Instructors' Day\n"
            "• December 8 — Constitution Day of Uzbekistan\n"
            "• Ramadan Hayit (2 days)\n"
            "• Qurbon Hayit (2 days)\n\n"
            "<b>Work on a public holiday (Article 157):</b>\n"
            "• <b>Double</b> pay, or\n"
            "• Regular pay + <b>a day off on another day</b> (at the employee's choice)\n\n"
            "<b>Important:</b> If a public holiday falls on a weekday (Mon–Fri), it is moved to the preceding or following working day — this is announced by a resolution of the Cabinet of Ministers."
        ),
        "source_label": "Labour Code, Articles 146–149",
    },
    "labor-dispute": {
        "title": "Procedure for resolving labour disputes",
        "summary": (
            "An individual dispute is first heard by the labour dispute "
            "commission, then by the court. Claims regarding unlawful "
            "dismissal must be filed in court within 1 month."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 271–275</b>\n\n"
            "<b>Types of disputes:</b>\n"
            "• <b>Individual dispute</b> — a disagreement between one employee and the employer\n"
            "• <b>Collective dispute</b> — involving a trade union or a group of employees\n\n"
            "<b>Procedure for hearing an individual dispute:</b>\n\n"
            "<b>Stage 1: Labour Dispute Commission (LDC)</b>\n"
            "• Formed within the enterprise (if it has 15+ employees)\n"
            "• Heard within <b>10 days</b> after the application is filed\n"
            "• The decision is executed within <b>10 days</b>\n\n"
            "<b>Stage 2: Court</b>\n"
            "• If the LDC's decision is contested, or if there is no LDC\n"
            "• For unlawful dismissal — the claim must be filed within <b>1 month</b>\n"
            "• For wage claims — within <b>3 years</b>\n"
            "• For other disputes — within <b>3 months</b>\n\n"
            "<b>Enforcement of the court decision:</b>\n"
            "A court decision on reinstatement must be enforced by the employer <b>immediately</b> (on the very next working day).\n\n"
            "<b>Labour inspection:</b>\n"
            "A complaint may be filed with the <b>labour inspectorate</b> at any time — it will conduct an inspection and impose a fine. This is not an alternative to court proceedings but runs in parallel."
        ),
        "source_label": "Labour Code, Articles 271–275",
    },
    "collective-agreement": {
        "title": "Collective agreement: what it is and why it matters",
        "summary": (
            "A collective agreement is an accord between the employer and the "
            "trade union (or employee representatives). It allows working "
            "conditions to be improved and additional benefits to be "
            "established."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 45–50</b>\n\n"
            "<b>What it is:</b>\n"
            "A collective agreement is a written accord concluded between the employer and employee representatives (a trade union or council of representatives). It provides for working conditions <b>better</b> than those set by law.\n\n"
            "<b>What it may include:</b>\n"
            "• A higher minimum wage (above the statutory MROT)\n"
            "• Additional leave days\n"
            "• Meal, transport, or housing benefits\n"
            "• Payment for healthcare or professional development\n"
            "• Higher compensation upon dismissal\n\n"
            "<b>Procedure for concluding (Article 47):</b>\n"
            "1. Employees or the trade union request the start of negotiations\n"
            "2. Negotiations are concluded within <b>3 months</b>\n"
            "3. After signing, the agreement is registered with the labour authorities within <b>7 days</b>\n"
            "4. Term of validity — usually <b>1–3 years</b>\n\n"
            "<b>Who it applies to:</b>\n"
            "The collective agreement applies to <b>all</b> employees of the enterprise where it is signed — even those who are not trade union members.\n\n"
            "<b>Important:</b> The terms of the collective agreement must be better than those of the individual employment contract; otherwise, the matter is resolved through the commission."
        ),
        "source_label": "Labour Code, Articles 45–50",
    },
    "labor-safety": {
        "title": "Occupational safety: employer obligations",
        "summary": (
            "The employer must create safe working conditions, provide "
            "protective equipment free of charge, and conduct safety "
            "briefings for employees."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 215–220, and the Law «On Occupational Safety» (2015)</b>\n\n"
            "<b>Main employer obligations (Article 215 of the Labour Code):</b>\n"
            "• Providing safe workplaces and equipment\n"
            "• Providing personal protective equipment (clothing, ear and eye protection) <b>free of charge</b>\n"
            "• Conducting an <b>occupational safety briefing</b> for newly hired employees\n"
            "• Informing employees about hazardous factors\n"
            "• Organizing medical examinations (for hazardous jobs)\n\n"
            "<b>Employee rights (Article 216):</b>\n"
            "• The right to safe working conditions\n"
            "• The <b>right to refuse</b> a hazardous work assignment\n"
            "• The right to compensation in case of injury or illness\n"
            "• The right to request an inspection of occupational safety conditions\n\n"
            "<b>Work injury (Article 218):</b>\n"
            "In the event of an injury at work:\n"
            "1. The employer immediately forms an investigation commission\n"
            "2. A report in Form N-1 is prepared (<b>within 3 days</b>)\n"
            "3. The injured party receives a lump-sum and monthly benefits from the <b>social insurance fund</b>\n\n"
            "<b>State oversight:</b>\n"
            "Labour inspectors may conduct unscheduled inspections of enterprises. If violations are found, a fine and suspension of operations may be applied."
        ),
        "source_label": "Law «On Occupational Safety», 2015 + Labour Code Articles 215–220",
    },
    "employment-guarantees": {
        "title": "Employment guarantees and unemployment benefits",
        "summary": (
            "The state supports officially unemployed persons through "
            "benefits, vocational training, and new job placements. "
            "Registering with the employment center is the main requirement."
        ),
        "full_text": (
            "📋 <b>Law «On State Support of the Population in the Sphere of Employment» (2021)</b>\n\n"
            "<b>State guarantees:</b>\n"
            "• Free assistance with job placement (through employment centers)\n"
            "• Vocational training and retraining courses — <b>free of charge</b>\n"
            "• Organizing temporary jobs\n"
            "• Unemployment benefits (for those registered)\n\n"
            "<b>Unemployment benefit:</b>\n"
            "• Received by those registered with the employment center\n"
            "• Amount: based on the last salary, but at least the <b>MROT</b> level\n"
            "• Duration: usually <b>up to 6 months</b> (12 months in special cases)\n"
            "• Active job searching is required while receiving the benefit\n\n"
            "<b>Applying to the employment center:</b>\n"
            "1. Apply with a passport and employment record book\n"
            "2. The first job offer is made within <b>10 days</b>\n"
            "3. Refusing offers three times results in loss of the benefit\n\n"
            "<b>Priority categories (given priority assistance):</b>\n"
            "• Persons with disabilities\n"
            "• Young specialists (under 25)\n"
            "• Parents of three or more children\n"
            "• Persons released from places of confinement, and others\n\n"
            "<b>Important:</b> Employment centers now also provide services online via the «Mehnat» portal: <b>mehnat.uz</b>"
        ),
        "source_label": "Employment Law, 2021 + Labour Code",
    },
    "trade-unions": {
        "title": "Trade unions and employee representation rights",
        "summary": (
            "Employees have the right to freely join and leave a trade union. "
            "Dismissal of trade union members is restricted."
        ),
        "full_text": (
            "📋 <b>Law «On Trade Unions» (1992, as amended)</b>\n\n"
            "<b>What a trade union is:</b>\n"
            "A trade union (TU) is a voluntary association of employees that protects their economic and labour rights.\n\n"
            "<b>Main employee rights (Article 5 of the Law):</b>\n"
            "• <b>Freely joining and leaving</b> the trade union\n"
            "• No deductions from wages for trade union activities\n"
            "• Allotting working time for the union representative to resolve issues\n\n"
            "<b>Trade union rights:</b>\n"
            "• Concluding and signing the collective agreement\n"
            "• Investigating violations of labour law\n"
            "• Conducting negotiations with the employer\n"
            "• Organizing a strike (in the manner prescribed by law)\n"
            "• Applying to court on behalf of employees\n\n"
            "<b>Right to strike (Article 257 of the Labour Code):</b>\n"
            "• Before starting a strike — negotiations, mediation\n"
            "• For an official strike — <b>7 days'</b> advance notice\n"
            "• Healthcare, nuclear power plants, railways — the right to strike is restricted\n\n"
            "<b>Dismissal of a trade union member:</b>\n"
            "When dismissing trade union leaders and activists, the employer must obtain the <b>consent of the trade union</b> (Article 101 of the Labour Code).\n\n"
            "<b>Important:</b> The same collective agreement terms also apply to those who are not trade union members."
        ),
        "source_label": "Law on Trade Unions, 1992 (as amended)",
    },
    "social-insurance": {
        "title": "State social insurance: who pays, who receives",
        "summary": (
            "The employer pays social insurance contributions for every "
            "officially employed worker. The employee receives sickness, "
            "injury, maternity, and pension benefits from this fund."
        ),
        "full_text": (
            "📋 <b>Law «On State Social Insurance»</b>\n\n"
            "<b>Types of insurance:</b>\n"
            "• Temporary incapacity for work (sick leave certificate)\n"
            "• Pregnancy and childbirth benefit\n"
            "• Childcare benefit (up to age 3)\n"
            "• Benefit for work injury and occupational disease\n"
            "• Pension (old-age, disability, survivor's)\n\n"
            "<b>Paying contributions (employer's obligation):</b>\n"
            "• A contribution calculated as a set percentage of official wages is transferred to the social insurance fund every month\n"
            "• The employee does not take part in paying the insurance contribution (the employer pays it in full)\n"
            "• Informal work provides no insurance protection\n\n"
            "<b>Amount of benefits:</b>\n"
            "Sickness or injury benefit depending on length of service:\n"
            "• Under 5 years — <b>60%</b> of wages\n"
            "• 5–8 years — <b>80%</b>\n"
            "• Over 8 years — <b>100%</b>\n\n"
            "<b>Risks of informal work:</b>\n"
            "For those working informally («off the books»):\n"
            "• No sick leave benefit\n"
            "• Limited compensation for work injury\n"
            "• Not counted toward pension service\n"
            "• No legal protection upon dismissal\n\n"
            "<b>Important:</b> If the employer does not officially register the employee, this is grounds for <b>administrative and criminal liability</b>."
        ),
        "source_label": "Law on State Social Insurance",
    },
    "pension-basics": {
        "title": "Pension provision: age and amount",
        "summary": (
            "Women retire at 55, men at 60. The pension amount depends on "
            "length of service and wages. A minimum pension is established."
        ),
        "full_text": (
            "📋 <b>Law «On Pension Provision» (LRU-783, 2023)</b>\n\n"
            "<b>Retirement age:</b>\n"
            "• Men — <b>60 years</b>\n"
            "• Women — <b>55 years</b>\n"
            "• Possibility of early retirement: for certain occupations (miners, hazardous work) — 5–10 years earlier\n\n"
            "<b>Minimum service:</b>\n"
            "An ordinary pension requires at least <b>25 years of service</b> (20 years for women).\n"
            "If the service is insufficient, a social pension (of a lower amount) is granted.\n\n"
            "<b>How the pension amount is calculated:</b>\n"
            "• A base portion + a supplement depending on length of service\n"
            "• A certain percentage of wages is added for each year of service\n"
            "• Calculated based on average wages over the last 3–5 years\n\n"
            "<b>Social pension (if service is insufficient):</b>\n"
            "Citizens without full service also receive a pension — at the established minimum amount.\n\n"
            "<b>Informal work and pension:</b>\n"
            "Years of informal work are not counted toward service — this leads to a smaller pension in the future.\n\n"
            "<b>Applying for a pension:</b>\n"
            "Upon reaching retirement age, apply to the <b>social service centers</b> or through the «My.gov.uz» portal."
        ),
        "source_label": "Law on Pension Provision (LRU-783, 2023)",
    },
    "labor-migration": {
        "title": "Working abroad: rights and important warnings",
        "summary": (
            "Traveling abroad through official Uzbek agencies is safe. Going "
            "through an unofficial broker may lead to the risk of human "
            "trafficking."
        ),
        "full_text": (
            "📋 <b>Labour Code Article 10 and the Law «On Labour Migration»</b>\n\n"
            "<b>Official employment abroad:</b>\n"
            "• Through licensed agencies approved by the Ministry of Employment and Labour Relations of Uzbekistan\n"
            "• Through the «International Labour Migration» agency (AMIR)\n"
            "• With the assistance of the Uzbek embassy abroad\n\n"
            "<b>An official contract is mandatory (Article 10 of the Labour Code):</b>\n"
            "To work abroad, you need:\n"
            "1. An official employment contract with the employer (in Uzbek and the foreign language)\n"
            "2. The contract must specify: place of work, salary, visa, housing, and a guarantee of return\n"
            "3. Registration with the Uzbek embassy\n\n"
            "<b>Warning signs (human trafficking):</b>\n"
            "🔴 An employer who confiscates your passport\n"
            "🔴 Work different from what is specified in the contract\n"
            "🔴 Non-payment of the promised salary\n"
            "🔴 Restriction of freedom or preventing return home\n\n"
            "<b>Where to seek help:</b>\n"
            "• The Uzbek embassy or consulate\n"
            "• «1404» — hotline (Uzbekistan)\n"
            "• IOM (International Organization for Migration)\n\n"
            "<b>Important:</b> Before signing any document, obtain an official translation and independent advice."
        ),
        "source_label": "Labour Code, Article 10 + Law on Labour Migration",
    },
    "labor-inspection": {
        "title": "Labour inspection: inspections and filing complaints",
        "summary": (
            "Labour inspectors conduct scheduled and unscheduled inspections "
            "at enterprises. Any employee may file a written complaint."
        ),
        "full_text": (
            "📋 <b>Labour Code, Articles 285–289, and the Inspection Regulations</b>\n\n"
            "<b>Tasks of the state labour inspectorate:</b>\n"
            "• Monitoring compliance with labour law and occupational safety requirements\n"
            "• Explaining labour rights to employees\n"
            "• Imposing fines when violations of the law are found\n\n"
            "<b>How an employee can file a complaint:</b>\n"
            "1. A <b>written application</b> — in person or by mail to the territorial labour inspectorate\n"
            "2. <b>Online</b> — via the «mehnat.uz» or «my.gov.uz» portal\n"
            "3. <b>By phone</b> — 1088 (Ministry of Employment hotline)\n\n"
            "<b>What happens as a result of the inspection:</b>\n"
            "• The inspector visits the enterprise and checks the documents\n"
            "• If a violation is found, an <b>order</b> is issued (with a deadline for correction)\n"
            "• Fine: for legal entities — up to <b>100–500 BCV</b>\n"
            "• Repeating the same violation — leads to a measure of <b>suspension of operations</b>\n\n"
            "<b>Protection of the complainant:</b>\n"
            "If the employer retaliates against an employee who filed a complaint, this is grounds for <b>separate liability</b> (Article 285 of the Labour Code).\n\n"
            "<b>Important:</b> Filing a complaint with the inspectorate is free, and anonymity can also be requested."
        ),
        "source_label": "Labour Code, Articles 285–289",
    },
}
