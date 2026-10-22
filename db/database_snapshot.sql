--
-- PostgreSQL database dump
--

\restrict eZr2roWhK334AS7nGcEmo1wcbWMS3guZYxA4GJTOyTtue0ySvgaYqbG6YGAwTAj

-- Dumped from database version 18.4 (Debian 18.4-1)
-- Dumped by pg_dump version 18.4 (Debian 18.4-1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: district_cfsva_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.district_cfsva_metrics (
    id integer NOT NULL,
    region_id integer NOT NULL,
    survey_year integer NOT NULL,
    fies_moderate_severe_pct double precision NOT NULL,
    fies_severe_pct double precision NOT NULL,
    food_consumption_score double precision NOT NULL,
    fcs_poor_pct double precision NOT NULL,
    hdds double precision NOT NULL,
    stunting_pct double precision NOT NULL,
    wasting_pct double precision NOT NULL,
    rcsi double precision NOT NULL,
    harvest_loss_pct double precision NOT NULL
);


--
-- Name: district_cfsva_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.district_cfsva_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: district_cfsva_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.district_cfsva_metrics_id_seq OWNED BY public.district_cfsva_metrics.id;


--
-- Name: indicators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.indicators (
    id integer NOT NULL,
    indicator_code character varying(64) NOT NULL,
    indicator_name character varying(128) NOT NULL,
    category character varying(64) NOT NULL,
    unit character varying(24) NOT NULL,
    description character varying(256) NOT NULL
);


--
-- Name: indicators_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.indicators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: indicators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.indicators_id_seq OWNED BY public.indicators.id;


--
-- Name: national_targets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.national_targets (
    id integer NOT NULL,
    target_key character varying(64) NOT NULL,
    value double precision NOT NULL,
    updated_by character varying(64) NOT NULL,
    updated_at character varying(32) NOT NULL
);


--
-- Name: national_targets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.national_targets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: national_targets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.national_targets_id_seq OWNED BY public.national_targets.id;


--
-- Name: regions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.regions (
    id integer NOT NULL,
    province character varying(64) NOT NULL,
    district character varying(64) NOT NULL,
    area_type character varying(16) NOT NULL,
    population_weight double precision NOT NULL
);


--
-- Name: regions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.regions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: regions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.regions_id_seq OWNED BY public.regions.id;


--
-- Name: survey_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.survey_metrics (
    id integer NOT NULL,
    region_id integer NOT NULL,
    indicator_id integer NOT NULL,
    survey_year integer NOT NULL,
    value double precision NOT NULL
);


--
-- Name: survey_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.survey_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: survey_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.survey_metrics_id_seq OWNED BY public.survey_metrics.id;


--
-- Name: district_cfsva_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.district_cfsva_metrics ALTER COLUMN id SET DEFAULT nextval('public.district_cfsva_metrics_id_seq'::regclass);


--
-- Name: indicators id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.indicators ALTER COLUMN id SET DEFAULT nextval('public.indicators_id_seq'::regclass);


--
-- Name: national_targets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.national_targets ALTER COLUMN id SET DEFAULT nextval('public.national_targets_id_seq'::regclass);


--
-- Name: regions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions ALTER COLUMN id SET DEFAULT nextval('public.regions_id_seq'::regclass);


--
-- Name: survey_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.survey_metrics ALTER COLUMN id SET DEFAULT nextval('public.survey_metrics_id_seq'::regclass);


--
-- Data for Name: district_cfsva_metrics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.district_cfsva_metrics (id, region_id, survey_year, fies_moderate_severe_pct, fies_severe_pct, food_consumption_score, fcs_poor_pct, hdds, stunting_pct, wasting_pct, rcsi, harvest_loss_pct) FROM stdin;
1	1	2024	3.98	0.23	54.3	7.4	6.3	25.8	1.8	11.3	18.8
2	2	2024	4.02	0.42	54.6	6.7	6.8	26	1.1	11.1	19.3
3	3	2024	3.98	2.76	54.7	6.9	6	25.6	1.6	11.8	18.5
4	4	2024	12.04	0.38	49.7	8.6	6.2	29.3	2.5	12.7	22.2
5	5	2024	13.21	1.11	47.8	9.5	6.7	29.7	2	13	24.1
6	6	2024	13.3	1.13	47.6	9.9	6.6	29.4	2.3	14	23.3
7	7	2024	14.05	1.04	46.5	10.9	6.1	30.8	2.6	13.7	24.9
8	8	2024	14.1	0.99	46.3	10.8	5.6	31	2.7	13.9	25.3
9	9	2024	15.08	1.1	46	10.7	6.1	31.2	2.2	14.5	26.6
10	10	2024	16.6	1.42	42.2	11.4	5.8	32.5	2	14.4	27.6
11	11	2024	22.82	1.1	49.1	9.1	6	29.6	2.2	13.5	22.7
12	12	2024	24.94	0.36	48	9.2	6.3	29.5	2.3	13	23.4
13	13	2024	25.33	1.05	47.2	9.7	6.4	30.7	2	14.1	24.7
14	14	2024	30.22	1.04	43.8	11.8	6.1	31.9	2.2	14.7	26.4
15	15	2024	30.4	1.46	44.1	11.9	6.2	31.7	2	15.1	27.3
16	16	2024	13.71	0.71	50.3	9	6.7	28.3	1.4	13.4	21.5
17	17	2024	13.52	1	50.5	8.8	6.5	28.6	1.9	12.7	22.2
18	18	2024	15.67	1.11	47.5	9.3	6.5	29.8	2	12.9	24.4
19	19	2024	16	0.5	47.1	9.9	6.2	30.6	2.1	13.2	23.6
20	20	2024	15.25	0.99	47.6	9.3	6.6	29.7	2.2	13.9	23.4
21	21	2024	18.19	0.95	43.8	11.8	5.9	31.9	2.4	14.9	26.5
22	22	2024	17.78	1.49	43.8	11.2	5.8	32.6	2	14.2	26.7
23	23	2024	18.04	1.33	44.2	11.6	5.4	31.8	2.8	14.5	26.2
24	24	2024	19.35	0.53	49.1	9.1	6.6	28.8	2	12.8	22.2
25	25	2024	20.17	1.17	48.7	9.4	5.6	29.5	2.4	13.2	23.3
26	26	2024	25.62	0.83	42.3	11.7	5.9	32.3	2	15.1	27.6
27	27	2024	24.93	1.5	43	11.8	6	32.5	2.7	14.9	27.1
28	28	2024	24.94	0.84	43.1	11	5.9	32.5	2.2	14.4	27.6
29	29	2024	24.35	0.89	43.1	11.2	6	32.6	2.2	14.7	26.5
30	30	2024	22.28	1.23	46.2	10	6.3	30.6	2.6	13.3	24.9
\.


--
-- Data for Name: indicators; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.indicators (id, indicator_code, indicator_name, category, unit, description) FROM stdin;
1	financial_inclusion_rate	Financial Inclusion Rate	Financial Inclusion	%	Share of adults served by formal + informal mechanisms (FinScope 2024: 96%)
2	formal_inclusion	Formal Inclusion Rate	Financial Inclusion	%	Share of adults formally served - bank, MFI, mobile wallet or SACCO (FinScope 2024: 92%)
3	transactional_account	Transactional Account Ownership	Financial Inclusion	%	Adults holding a bank, mobile wallet or other transactional account (FinScope 2024: 77%)
4	mobile_money	Mobile Money Usage	Financial Inclusion	%	Adults using mobile wallets (FinScope 2024: 77%)
5	financial_exclusion_rate	Financial Exclusion Rate	Financial Inclusion	%	Adults excluded from all financial mechanisms (FinScope 2024: 4%)
6	formal_credit	Formal Credit Usage	Financial Inclusion	%	Adults borrowing from formal institutions (FinScope 2024: 24%)
7	formal_savings	Formal Savings Uptake	Financial Inclusion	%	Adults saving formally / semi-formally (FinScope 2024: 59%)
8	poverty_headcount	Poverty Headcount Rate	Poverty Dynamics	%	Population below the national basic-needs poverty line (EICV7: 27.4%)
9	extreme_poverty_rate	Extreme Poverty Rate	Poverty Dynamics	%	Population below the food-poverty line (EICV7: 4.5%)
10	social_protection	Social Protection Coverage	Social Protection	%	Households reached by at least one social protection programme (EICV7: 61.3%)
11	vup_public_works	VUP Public Works Participation	Social Protection	%	Household members engaged in VUP public works (EICV7 VUP; TUNABLE: 21%)
12	vup_direct_support	VUP Direct Support Reach	Social Protection	%	Households receiving VUP direct support grants (EICV7 VUP; TUNABLE: 9.5%)
13	climate_shock	Climate Shock Exposure	Climate Resilience	%	Adults hit by floods, droughts or storms in the last 12 months (FinScope 2024: 69%)
14	financial_health	Financially Healthy Share	Financial Health	%	Adults that are financially healthy (FinScope 2024: 10%)
15	financially_coping	Financially Coping Share	Financial Health	%	Adults that are financially coping (FinScope 2024: 57%)
16	financially_vulnerable	Financially Vulnerable Share	Financial Health	%	Adults that are financially vulnerable (FinScope 2024: 31%)
17	extremely_vulnerable	Extremely Vulnerable Share	Financial Health	%	Adults that are extremely vulnerable (FinScope 2024: 3%)
18	electricity_access	Electricity Access	Living Conditions	%	Households with electricity (grid or solar) (EICV7: 72%)
19	improved_water	Improved Water Source Access	Living Conditions	%	Households accessing improved water sources (EICV7: 90%)
20	modern_flooring	Modern Solid Flooring	Living Conditions	%	Households with solid modern flooring (cement/carpet) (EICV7; TUNABLE: 25%)
\.


--
-- Data for Name: national_targets; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.national_targets (id, target_key, value, updated_by, updated_at) FROM stdin;
\.


--
-- Data for Name: regions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.regions (id, province, district, area_type, population_weight) FROM stdin;
1	Kigali City	Nyarugenge	urban	0.433
2	Kigali City	Gasabo	urban	0.879
3	Kigali City	Kicukiro	urban	0.479
4	Eastern Province	Nyagatare	mixed	0.548
5	Eastern Province	Rwamagana	rural	0.449
6	Eastern Province	Ngoma	rural	0.368
7	Eastern Province	Kayonza	rural	0.445
8	Eastern Province	Gatsibo	rural	0.434
9	Eastern Province	Bugesera	rural	0.478
10	Eastern Province	Kirehe	rural	0.424
11	Northern Province	Musanze	mixed	0.532
12	Northern Province	Rulindo	rural	0.404
13	Northern Province	Gicumbi	rural	0.455
14	Northern Province	Burera	rural	0.396
15	Northern Province	Gakenke	rural	0.353
16	Southern Province	Huye	mixed	0.47
17	Southern Province	Muhanga	mixed	0.397
18	Southern Province	Kamonyi	rural	0.605
19	Southern Province	Ruhango	rural	0.382
20	Southern Province	Nyanza	rural	0.331
21	Southern Province	Nyamagabe	rural	0.527
22	Southern Province	Nyaruguru	rural	0.325
23	Southern Province	Gisagara	rural	0.381
24	Western Province	Rubavu	mixed	0.431
25	Western Province	Rusizi	mixed	0.397
26	Western Province	Karongi	rural	0.321
27	Western Province	Nyamasheke	rural	0.426
28	Western Province	Rutsiro	rural	0.369
29	Western Province	Ngororero	rural	0.41
30	Western Province	Nyabihu	rural	0.326
\.


--
-- Data for Name: survey_metrics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.survey_metrics (id, region_id, indicator_id, survey_year, value) FROM stdin;
1	1	1	2024	99.3
2	1	2	2024	96.1
3	1	3	2024	86.4
4	1	4	2024	87.4
5	1	5	2024	1
6	1	6	2024	37.5
7	1	7	2024	67.9
8	1	8	2024	19.6
9	1	9	2024	2.6
10	1	10	2024	68.6
11	1	11	2024	14
12	1	12	2024	6.1
13	1	13	2024	54.4
14	1	14	2024	13
15	1	15	2024	58.8
16	1	16	2024	25.7
17	1	17	2024	2.5
18	1	18	2024	90.8
19	1	19	2024	97.9
20	1	20	2024	37.4
21	2	1	2024	99
22	2	2	2024	95.6
23	2	3	2024	86.3
24	2	4	2024	87.6
25	2	5	2024	1
26	2	6	2024	35.9
27	2	7	2024	67.8
28	2	8	2024	19.6
29	2	9	2024	2.3
30	2	10	2024	68.8
31	2	11	2024	14.4
32	2	12	2024	6.9
33	2	13	2024	54.4
34	2	14	2024	15.3
35	2	15	2024	55.9
36	2	16	2024	26.3
37	2	17	2024	2.5
38	2	18	2024	90.4
39	2	19	2024	96.9
40	2	20	2024	38
41	3	1	2024	99.1
42	3	2	2024	95.6
43	3	3	2024	86.9
44	3	4	2024	86.9
45	3	5	2024	1
46	3	6	2024	33.3
47	3	7	2024	70.3
48	3	8	2024	19.7
49	3	9	2024	2.6
50	3	10	2024	68.4
51	3	11	2024	14.3
52	3	12	2024	6
53	3	13	2024	54.2
54	3	14	2024	13.1
55	3	15	2024	57.8
56	3	16	2024	26.5
57	3	17	2024	2.6
58	3	18	2024	90.2
59	3	19	2024	97.4
60	3	20	2024	37.4
61	4	1	2024	98.9
62	4	2	2024	95
63	4	3	2024	82
64	4	4	2024	83.1
65	4	5	2024	1.1
66	4	6	2024	28.1
67	4	7	2024	65
68	4	8	2024	25.7
69	4	9	2024	4
70	4	10	2024	64
71	4	11	2024	18.8
72	4	12	2024	8.7
73	4	13	2024	62.8
74	4	14	2024	11.2
75	4	15	2024	57.7
76	4	16	2024	28.4
77	4	17	2024	2.7
78	4	18	2024	80.2
79	4	19	2024	92.5
80	4	20	2024	29
81	5	1	2024	97.3
82	5	2	2024	92.5
83	5	3	2024	78.3
84	5	4	2024	78.8
85	5	5	2024	2.7
86	5	6	2024	24.1
87	5	7	2024	59.9
88	5	8	2024	27.2
89	5	9	2024	4.3
90	5	10	2024	62.5
91	5	11	2024	20
92	5	12	2024	8.4
93	5	13	2024	68.3
94	5	14	2024	10.2
95	5	15	2024	56.8
96	5	16	2024	30.1
97	5	17	2024	2.9
98	5	18	2024	71.2
99	5	19	2024	91
100	5	20	2024	25.3
101	6	1	2024	96.6
102	6	2	2024	93.2
103	6	3	2024	77.6
104	6	4	2024	78.9
105	6	5	2024	3.4
106	6	6	2024	24.9
107	6	7	2024	60
108	6	8	2024	27
109	6	9	2024	4
110	6	10	2024	62.2
111	6	11	2024	20.5
112	6	12	2024	8.9
113	6	13	2024	68.4
114	6	14	2024	10
115	6	15	2024	56.1
116	6	16	2024	30.9
117	6	17	2024	3
118	6	18	2024	71.5
119	6	19	2024	90.4
120	6	20	2024	25.2
121	7	1	2024	94.1
122	7	2	2024	90.3
123	7	3	2024	73.5
124	7	4	2024	74
125	7	5	2024	5.9
126	7	6	2024	20.9
127	7	7	2024	56.2
128	7	8	2024	28.8
129	7	9	2024	4.6
130	7	10	2024	59.2
131	7	11	2024	22.9
132	7	12	2024	9.7
133	7	13	2024	71.3
134	7	14	2024	9.4
135	7	15	2024	54.3
136	7	16	2024	33.1
137	7	17	2024	3.2
138	7	18	2024	66.2
139	7	19	2024	87.3
140	7	20	2024	21.8
141	8	1	2024	95.1
142	8	2	2024	91.1
143	8	3	2024	73.8
144	8	4	2024	73.6
145	8	5	2024	4.9
146	8	6	2024	20.7
147	8	7	2024	56.1
148	8	8	2024	28.9
149	8	9	2024	4.6
150	8	10	2024	59.8
151	8	11	2024	23.2
152	8	12	2024	9.9
153	8	13	2024	70.9
154	8	14	2024	9.1
155	8	15	2024	55
156	8	16	2024	32.7
157	8	17	2024	3.2
158	8	18	2024	66.9
159	8	19	2024	88.3
160	8	20	2024	21.7
161	9	1	2024	94.2
162	9	2	2024	90.9
163	9	3	2024	73.3
164	9	4	2024	67.9
165	9	5	2024	5.8
166	9	6	2024	20.9
167	9	7	2024	56.2
168	9	8	2024	28.8
169	9	9	2024	4.8
170	9	10	2024	59.7
171	9	11	2024	22.5
172	9	12	2024	10.4
173	9	13	2024	79.7
174	9	14	2024	8.3
175	9	15	2024	56.6
176	9	16	2024	32
177	9	17	2024	3.1
178	9	18	2024	66.3
179	9	19	2024	87.7
180	9	20	2024	21.2
181	10	1	2024	92.7
182	10	2	2024	88
183	10	3	2024	70.4
184	10	4	2024	68.5
185	10	5	2024	7.3
186	10	6	2024	17.5
187	10	7	2024	51
188	10	8	2024	32.8
189	10	9	2024	6.4
190	10	10	2024	56
191	10	11	2024	25.7
192	10	12	2024	12.1
193	10	13	2024	80.6
194	10	14	2024	7.5
195	10	15	2024	54.7
196	10	16	2024	34.5
197	10	17	2024	3.3
198	10	18	2024	59.9
199	10	19	2024	85.2
200	10	20	2024	17.9
201	11	1	2024	98.7
202	11	2	2024	94
203	11	3	2024	81.9
204	11	4	2024	85
205	11	5	2024	1.3
206	11	6	2024	28.2
207	11	7	2024	64.4
208	11	8	2024	25.6
209	11	9	2024	3.5
210	11	10	2024	63.9
211	11	11	2024	19.5
212	11	12	2024	7.9
213	11	13	2024	63.1
214	11	14	2024	11.5
215	11	15	2024	56.6
216	11	16	2024	29.1
217	11	17	2024	2.8
218	11	18	2024	80.2
219	11	19	2024	92.8
220	11	20	2024	29.5
221	12	1	2024	97.6
222	12	2	2024	92.9
223	12	3	2024	77.6
224	12	4	2024	78
225	12	5	2024	2.4
226	12	6	2024	24.5
227	12	7	2024	60.3
228	12	8	2024	26.7
229	12	9	2024	4
230	12	10	2024	62.1
231	12	11	2024	20
232	12	12	2024	8.3
233	12	13	2024	68.9
234	12	14	2024	9.6
235	12	15	2024	56.7
236	12	16	2024	30.7
237	12	17	2024	3
238	12	18	2024	71.3
239	12	19	2024	89.8
240	12	20	2024	24.9
241	13	1	2024	96.1
242	13	2	2024	93.3
243	13	3	2024	77.3
244	13	4	2024	78.3
245	13	5	2024	3.9
246	13	6	2024	24.8
247	13	7	2024	61
248	13	8	2024	27.4
249	13	9	2024	4.2
250	13	10	2024	61.8
251	13	11	2024	20.4
252	13	12	2024	9
253	13	13	2024	71.3
254	13	14	2024	9.7
255	13	15	2024	56.7
256	13	16	2024	30.6
257	13	17	2024	3
258	13	18	2024	71.4
259	13	19	2024	90.2
260	13	20	2024	25.3
261	14	1	2024	92.6
262	14	2	2024	88.4
263	14	3	2024	70.6
264	14	4	2024	68.8
265	14	5	2024	7.4
266	14	6	2024	16.9
267	14	7	2024	52
268	14	8	2024	31.3
269	14	9	2024	6.2
270	14	10	2024	55.3
271	14	11	2024	25.6
272	14	12	2024	12.1
273	14	13	2024	76
274	14	14	2024	7.4
275	14	15	2024	54.9
276	14	16	2024	34.4
277	14	17	2024	3.3
278	14	18	2024	60.1
279	14	19	2024	85.6
280	14	20	2024	17.6
281	15	1	2024	91.9
282	15	2	2024	88.8
283	15	3	2024	70
284	15	4	2024	69
285	15	5	2024	8.1
286	15	6	2024	17.5
287	15	7	2024	48.5
288	15	8	2024	31.1
289	15	9	2024	5.6
290	15	10	2024	55.4
291	15	11	2024	24.9
292	15	12	2024	12.4
293	15	13	2024	80.5
294	15	14	2024	8
295	15	15	2024	53.9
296	15	16	2024	34.7
297	15	17	2024	3.4
298	15	18	2024	60.3
299	15	19	2024	85.2
300	15	20	2024	16.7
301	16	1	2024	98.8
302	16	2	2024	94.2
303	16	3	2024	82.4
304	16	4	2024	82.6
305	16	5	2024	1.2
306	16	6	2024	28.1
307	16	7	2024	64.7
308	16	8	2024	24.5
309	16	9	2024	4.2
310	16	10	2024	64.6
311	16	11	2024	18.5
312	16	12	2024	8.4
313	16	13	2024	62.7
314	16	14	2024	11.4
315	16	15	2024	57.5
316	16	16	2024	28.4
317	16	17	2024	2.7
318	16	18	2024	81.1
319	16	19	2024	92.9
320	16	20	2024	29.1
321	17	1	2024	99.2
322	17	2	2024	94.1
323	17	3	2024	82.1
324	17	4	2024	82.1
325	17	5	2024	1
326	17	6	2024	28.9
327	17	7	2024	64.5
328	17	8	2024	24.6
329	17	9	2024	4.2
330	17	10	2024	63.9
331	17	11	2024	19
332	17	12	2024	8.1
333	17	13	2024	63.5
334	17	14	2024	11.3
335	17	15	2024	57.6
336	17	16	2024	28.4
337	17	17	2024	2.7
338	17	18	2024	80.3
339	17	19	2024	92.8
340	17	20	2024	29.6
341	18	1	2024	96.8
342	18	2	2024	93.5
343	18	3	2024	77.3
344	18	4	2024	78.1
345	18	5	2024	3.2
346	18	6	2024	24.7
347	18	7	2024	60.9
348	18	8	2024	26.8
349	18	9	2024	4.2
350	18	10	2024	62.7
351	18	11	2024	20.2
352	18	12	2024	8.8
353	18	13	2024	69
354	18	14	2024	10.1
355	18	15	2024	56.6
356	18	16	2024	30.4
357	18	17	2024	2.9
358	18	18	2024	72.1
359	18	19	2024	90.4
360	18	20	2024	25.3
361	19	1	2024	97
362	19	2	2024	92.5
363	19	3	2024	77.6
364	19	4	2024	78
365	19	5	2024	3
366	19	6	2024	24.8
367	19	7	2024	60.8
368	19	8	2024	27.6
369	19	9	2024	4.5
370	19	10	2024	62.1
371	19	11	2024	20.4
372	19	12	2024	8.9
373	19	13	2024	68.2
374	19	14	2024	9.7
375	19	15	2024	57.4
376	19	16	2024	30
377	19	17	2024	2.9
378	19	18	2024	71.1
379	19	19	2024	90.8
380	19	20	2024	25.2
381	20	1	2024	97.1
382	20	2	2024	93.3
383	20	3	2024	78
384	20	4	2024	78.3
385	20	5	2024	2.9
386	20	6	2024	24.9
387	20	7	2024	60.6
388	20	8	2024	26.8
389	20	9	2024	4.8
390	20	10	2024	62.3
391	20	11	2024	20
392	20	12	2024	8.8
393	20	13	2024	69.2
394	20	14	2024	10.3
395	20	15	2024	56.5
396	20	16	2024	30.3
397	20	17	2024	2.9
398	20	18	2024	71.1
399	20	19	2024	89.9
400	20	20	2024	26
401	21	1	2024	92.7
402	21	2	2024	88.1
403	21	3	2024	69.9
404	21	4	2024	69.1
405	21	5	2024	7.3
406	21	6	2024	17.4
407	21	7	2024	51.5
408	21	8	2024	32.4
409	21	9	2024	6
410	21	10	2024	57.3
411	21	11	2024	24.8
412	21	12	2024	12.4
413	21	13	2024	75.1
414	21	14	2024	7.9
415	21	15	2024	53.9
416	21	16	2024	34.8
417	21	17	2024	3.4
418	21	18	2024	60.7
419	21	19	2024	85.1
420	21	20	2024	16.9
421	22	1	2024	93
422	22	2	2024	88.8
423	22	3	2024	70
424	22	4	2024	69.6
425	22	5	2024	7
426	22	6	2024	14.4
427	22	7	2024	48
428	22	8	2024	31.6
429	22	9	2024	5.7
430	22	10	2024	55.9
431	22	11	2024	25.5
432	22	12	2024	12.3
433	22	13	2024	75.2
434	22	14	2024	7.7
435	22	15	2024	54.6
436	22	16	2024	34.4
437	22	17	2024	3.3
438	22	18	2024	60
439	22	19	2024	85.2
440	22	20	2024	17
441	23	1	2024	92.9
442	23	2	2024	88.6
443	23	3	2024	69.9
444	23	4	2024	66.6
445	23	5	2024	7.1
446	23	6	2024	17.2
447	23	7	2024	49.2
448	23	8	2024	31.4
449	23	9	2024	5.6
450	23	10	2024	55.7
451	23	11	2024	25.3
452	23	12	2024	12
453	23	13	2024	75.6
454	23	14	2024	7.2
455	23	15	2024	54.5
456	23	16	2024	34.9
457	23	17	2024	3.4
458	23	18	2024	60.4
459	23	19	2024	85
460	23	20	2024	17.4
461	24	1	2024	98.7
462	24	2	2024	94.4
463	24	3	2024	81.6
464	24	4	2024	84.8
465	24	5	2024	1.3
466	24	6	2024	27.5
467	24	7	2024	64.6
468	24	8	2024	26.1
469	24	9	2024	3.7
470	24	10	2024	64.2
471	24	11	2024	18.9
472	24	12	2024	8.1
473	24	13	2024	63.1
474	24	14	2024	11.4
475	24	15	2024	56.9
476	24	16	2024	28.9
477	24	17	2024	2.8
478	24	18	2024	80.7
479	24	19	2024	92.9
480	24	20	2024	29.9
481	25	1	2024	99.1
482	25	2	2024	94.6
483	25	3	2024	82.4
484	25	4	2024	82.1
485	25	5	2024	1
486	25	6	2024	27.4
487	25	7	2024	64.3
488	25	8	2024	26.9
489	25	9	2024	4.3
490	25	10	2024	64.7
491	25	11	2024	19.2
492	25	12	2024	7.8
493	25	13	2024	62.7
494	25	14	2024	11.1
495	25	15	2024	57.5
496	25	16	2024	28.6
497	25	17	2024	2.8
498	25	18	2024	81
499	25	19	2024	92.9
500	25	20	2024	29.9
501	26	1	2024	92.1
502	26	2	2024	88.7
503	26	3	2024	70.1
504	26	4	2024	68.8
505	26	5	2024	7.9
506	26	6	2024	16.7
507	26	7	2024	51.8
508	26	8	2024	32.8
510	26	10	2024	55.7
511	26	11	2024	25.5
512	26	12	2024	12
513	26	13	2024	79.4
514	26	14	2024	7.9
515	26	15	2024	54.2
516	26	16	2024	34.6
517	26	17	2024	3.3
518	26	18	2024	60.4
519	26	19	2024	85.8
520	26	20	2024	16.9
521	27	1	2024	93.1
522	27	2	2024	88.1
523	27	3	2024	70.2
524	27	4	2024	69.1
525	27	5	2024	6.9
526	27	6	2024	17.1
527	27	7	2024	51
528	27	8	2024	32.4
529	27	9	2024	5.6
530	27	10	2024	55.7
531	27	11	2024	25.2
532	27	12	2024	12.1
533	27	13	2024	80.4
534	27	14	2024	7.8
535	27	15	2024	54.5
536	27	16	2024	34.4
537	27	17	2024	3.3
538	27	18	2024	60.4
539	27	19	2024	85.9
540	27	20	2024	17.4
541	28	1	2024	92.4
542	28	2	2024	88.2
543	28	3	2024	70.2
544	28	4	2024	69.5
545	28	5	2024	7.6
546	28	6	2024	16.7
547	28	7	2024	52
548	28	8	2024	31.1
549	28	9	2024	6.2
550	28	10	2024	56
551	28	11	2024	25.5
552	28	12	2024	11.9
553	28	13	2024	81.7
554	28	14	2024	7.9
555	28	15	2024	54.6
556	28	16	2024	34.2
557	28	17	2024	3.3
558	28	18	2024	60.8
559	28	19	2024	85.6
560	28	20	2024	17.8
561	29	1	2024	91.5
562	29	2	2024	88.2
563	29	3	2024	69.7
564	29	4	2024	68.9
565	29	5	2024	8.5
566	29	6	2024	15.1
567	29	7	2024	51.6
568	29	8	2024	32
569	29	9	2024	5.5
570	29	10	2024	55.9
571	29	11	2024	25.2
572	29	12	2024	12.5
573	29	13	2024	75.5
574	29	14	2024	7.4
575	29	15	2024	54.2
576	29	16	2024	35
577	29	17	2024	3.4
578	29	18	2024	60.9
579	29	19	2024	85
580	29	20	2024	17.8
581	30	1	2024	94.5
582	30	2	2024	90.4
583	30	3	2024	73.6
584	30	4	2024	74.4
585	30	5	2024	5.5
586	30	6	2024	20.9
587	30	7	2024	56.6
588	30	8	2024	28.6
589	30	9	2024	5.3
590	30	10	2024	59.2
591	30	11	2024	22.7
592	30	12	2024	9.7
593	30	13	2024	71.4
594	30	14	2024	9.1
595	30	15	2024	54.8
596	30	16	2024	32.9
597	30	17	2024	3.2
598	30	18	2024	65.9
599	30	19	2024	88.3
600	30	20	2024	21.3
509	26	9	2024	5.8
\.


--
-- Name: district_cfsva_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.district_cfsva_metrics_id_seq', 30, true);


--
-- Name: indicators_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.indicators_id_seq', 20, true);


--
-- Name: national_targets_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.national_targets_id_seq', 2, true);


--
-- Name: regions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.regions_id_seq', 30, true);


--
-- Name: survey_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.survey_metrics_id_seq', 600, true);


--
-- Name: district_cfsva_metrics district_cfsva_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.district_cfsva_metrics
    ADD CONSTRAINT district_cfsva_metrics_pkey PRIMARY KEY (id);


--
-- Name: indicators indicators_indicator_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.indicators
    ADD CONSTRAINT indicators_indicator_code_key UNIQUE (indicator_code);


--
-- Name: indicators indicators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.indicators
    ADD CONSTRAINT indicators_pkey PRIMARY KEY (id);


--
-- Name: national_targets national_targets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.national_targets
    ADD CONSTRAINT national_targets_pkey PRIMARY KEY (id);


--
-- Name: national_targets national_targets_target_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.national_targets
    ADD CONSTRAINT national_targets_target_key_key UNIQUE (target_key);


--
-- Name: regions regions_district_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions
    ADD CONSTRAINT regions_district_key UNIQUE (district);


--
-- Name: regions regions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions
    ADD CONSTRAINT regions_pkey PRIMARY KEY (id);


--
-- Name: survey_metrics survey_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.survey_metrics
    ADD CONSTRAINT survey_metrics_pkey PRIMARY KEY (id);


--
-- Name: district_cfsva_metrics uq_cfsva_region_year; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.district_cfsva_metrics
    ADD CONSTRAINT uq_cfsva_region_year UNIQUE (region_id, survey_year);


--
-- Name: survey_metrics uq_metric_region_indicator_year; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.survey_metrics
    ADD CONSTRAINT uq_metric_region_indicator_year UNIQUE (region_id, indicator_id, survey_year);


--
-- Name: ix_district_cfsva_metrics_region_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_district_cfsva_metrics_region_id ON public.district_cfsva_metrics USING btree (region_id);


--
-- Name: ix_indicators_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_indicators_category ON public.indicators USING btree (category);


--
-- Name: ix_regions_province; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regions_province ON public.regions USING btree (province);


--
-- Name: ix_survey_metrics_indicator_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_survey_metrics_indicator_id ON public.survey_metrics USING btree (indicator_id);


--
-- Name: ix_survey_metrics_region_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_survey_metrics_region_id ON public.survey_metrics USING btree (region_id);


--
-- Name: district_cfsva_metrics district_cfsva_metrics_region_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.district_cfsva_metrics
    ADD CONSTRAINT district_cfsva_metrics_region_id_fkey FOREIGN KEY (region_id) REFERENCES public.regions(id) ON DELETE CASCADE;


--
-- Name: survey_metrics survey_metrics_indicator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.survey_metrics
    ADD CONSTRAINT survey_metrics_indicator_id_fkey FOREIGN KEY (indicator_id) REFERENCES public.indicators(id) ON DELETE CASCADE;


--
-- Name: survey_metrics survey_metrics_region_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.survey_metrics
    ADD CONSTRAINT survey_metrics_region_id_fkey FOREIGN KEY (region_id) REFERENCES public.regions(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict eZr2roWhK334AS7nGcEmo1wcbWMS3guZYxA4GJTOyTtue0ySvgaYqbG6YGAwTAj

