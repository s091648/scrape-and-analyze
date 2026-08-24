/**
 * ISO 3166-1 alpha-2 → numeric-id mapping, scoped to exactly the 174 countries present in
 * `public/data/world-countries-110m.json` (Natural Earth 110m resolution via world-atlas —
 * small island nations like Singapore, Malta, or Vatican City are omitted at this resolution
 * since they'd render as sub-pixel dots on a world map anyway). The numeric ids are the
 * feature `id`s used by that topojson's country geometries; MaxMind GeoLite2 (see
 * shared/utils/geoip.py) returns alpha-2 codes, so this table is what joins a
 * `geo_country` value from the backend's request logs to a shape on the map.
 */
export const ISO_ALPHA2_TO_NUMERIC: Record<string, string> = {
  AF: '004', AL: '008', AQ: '010', DZ: '012', AO: '024', AZ: '031', AR: '032', AU: '036',
  AT: '040', BS: '044', BD: '050', AM: '051', BE: '056', BT: '064', BO: '068', BA: '070',
  BW: '072', BR: '076', BZ: '084', SB: '090', BN: '096', BG: '100', MM: '104', BI: '108',
  BY: '112', KH: '116', CM: '120', CA: '124', CF: '140', LK: '144', TD: '148', CL: '152',
  CN: '156', TW: '158', CO: '170', CG: '178', CD: '180', CR: '188', HR: '191', CU: '192',
  CY: '196', CZ: '203', BJ: '204', DK: '208', DO: '214', EC: '218', SV: '222', GQ: '226',
  ET: '231', ER: '232', EE: '233', FK: '238', FJ: '242', FI: '246', FR: '250', TF: '260',
  DJ: '262', GA: '266', GE: '268', GM: '270', PS: '275', DE: '276', GH: '288', GR: '300',
  GL: '304', GT: '320', GN: '324', GY: '328', HT: '332', HN: '340', HU: '348', IS: '352',
  IN: '356', ID: '360', IR: '364', IQ: '368', IE: '372', IL: '376', IT: '380', CI: '384',
  JM: '388', JP: '392', KZ: '398', JO: '400', KE: '404', KP: '408', KR: '410', KW: '414',
  KG: '417', LA: '418', LB: '422', LS: '426', LV: '428', LR: '430', LY: '434', LT: '440',
  LU: '442', MG: '450', MW: '454', MY: '458', ML: '466', MR: '478', MX: '484', MN: '496',
  MD: '498', ME: '499', MA: '504', MZ: '508', OM: '512', NA: '516', NP: '524', NL: '528',
  NC: '540', VU: '548', NZ: '554', NI: '558', NE: '562', NG: '566', NO: '578', PK: '586',
  PA: '591', PG: '598', PY: '600', PE: '604', PH: '608', PL: '616', PT: '620', GW: '624',
  TL: '626', PR: '630', QA: '634', RO: '642', RU: '643', RW: '646', SA: '682', SN: '686',
  RS: '688', SL: '694', SK: '703', VN: '704', SI: '705', SO: '706', ZA: '710', ZW: '716',
  ES: '724', SS: '728', SD: '729', EH: '732', SR: '740', SZ: '748', SE: '752', CH: '756',
  SY: '760', TJ: '762', TH: '764', TG: '768', TT: '780', AE: '784', TN: '788', TR: '792',
  TM: '795', UG: '800', UA: '804', MK: '807', EG: '818', GB: '826', TZ: '834', US: '840',
  BF: '854', UY: '858', UZ: '860', VE: '862', YE: '887', ZM: '894',
}

/** Reverse of ISO_ALPHA2_TO_NUMERIC — CountryMap needs this to go from a clicked map shape's
 * `geo.id` (numeric) back to the alpha-2 code CountryTable/the Loki query key on. */
export const ISO_NUMERIC_TO_ALPHA2: Record<string, string> = Object.fromEntries(
  Object.entries(ISO_ALPHA2_TO_NUMERIC).map(([alpha2, numeric]) => [numeric, alpha2]),
)

/** Display names for the same 174 countries, taken verbatim from the topojson's own
 * `properties.name` (Natural Earth) so a country's name in this table always matches what
 * CountryMap's hover tooltip shows for the same shape — some are the Natural Earth short
 * form (e.g. "Bosnia and Herz.", "Dem. Rep. Congo") rather than the full official name. */
export const ISO_ALPHA2_TO_NAME: Record<string, string> = {
  AF: 'Afghanistan', AL: 'Albania', AQ: 'Antarctica', DZ: 'Algeria', AO: 'Angola',
  AZ: 'Azerbaijan', AR: 'Argentina', AU: 'Australia', AT: 'Austria', BS: 'Bahamas',
  BD: 'Bangladesh', AM: 'Armenia', BE: 'Belgium', BT: 'Bhutan', BO: 'Bolivia',
  BA: 'Bosnia and Herz.', BW: 'Botswana', BR: 'Brazil', BZ: 'Belize', SB: 'Solomon Is.',
  BN: 'Brunei', BG: 'Bulgaria', MM: 'Myanmar', BI: 'Burundi', BY: 'Belarus',
  KH: 'Cambodia', CM: 'Cameroon', CA: 'Canada', CF: 'Central African Rep.', LK: 'Sri Lanka',
  TD: 'Chad', CL: 'Chile', CN: 'China', TW: 'Taiwan', CO: 'Colombia',
  CG: 'Congo', CD: 'Dem. Rep. Congo', CR: 'Costa Rica', HR: 'Croatia', CU: 'Cuba',
  CY: 'Cyprus', CZ: 'Czechia', BJ: 'Benin', DK: 'Denmark', DO: 'Dominican Rep.',
  EC: 'Ecuador', SV: 'El Salvador', GQ: 'Eq. Guinea', ET: 'Ethiopia', ER: 'Eritrea',
  EE: 'Estonia', FK: 'Falkland Is.', FJ: 'Fiji', FI: 'Finland', FR: 'France',
  TF: 'Fr. S. Antarctic Lands', DJ: 'Djibouti', GA: 'Gabon', GE: 'Georgia', GM: 'Gambia',
  PS: 'Palestine', DE: 'Germany', GH: 'Ghana', GR: 'Greece', GL: 'Greenland',
  GT: 'Guatemala', GN: 'Guinea', GY: 'Guyana', HT: 'Haiti', HN: 'Honduras',
  HU: 'Hungary', IS: 'Iceland', IN: 'India', ID: 'Indonesia', IR: 'Iran',
  IQ: 'Iraq', IE: 'Ireland', IL: 'Israel', IT: 'Italy', CI: "Côte d'Ivoire",
  JM: 'Jamaica', JP: 'Japan', KZ: 'Kazakhstan', JO: 'Jordan', KE: 'Kenya',
  KP: 'North Korea', KR: 'South Korea', KW: 'Kuwait', KG: 'Kyrgyzstan', LA: 'Laos',
  LB: 'Lebanon', LS: 'Lesotho', LV: 'Latvia', LR: 'Liberia', LY: 'Libya',
  LT: 'Lithuania', LU: 'Luxembourg', MG: 'Madagascar', MW: 'Malawi', MY: 'Malaysia',
  ML: 'Mali', MR: 'Mauritania', MX: 'Mexico', MN: 'Mongolia', MD: 'Moldova',
  ME: 'Montenegro', MA: 'Morocco', MZ: 'Mozambique', OM: 'Oman', NA: 'Namibia',
  NP: 'Nepal', NL: 'Netherlands', NC: 'New Caledonia', VU: 'Vanuatu', NZ: 'New Zealand',
  NI: 'Nicaragua', NE: 'Niger', NG: 'Nigeria', NO: 'Norway', PK: 'Pakistan',
  PA: 'Panama', PG: 'Papua New Guinea', PY: 'Paraguay', PE: 'Peru', PH: 'Philippines',
  PL: 'Poland', PT: 'Portugal', GW: 'Guinea-Bissau', TL: 'Timor-Leste', PR: 'Puerto Rico',
  QA: 'Qatar', RO: 'Romania', RU: 'Russia', RW: 'Rwanda', SA: 'Saudi Arabia',
  SN: 'Senegal', RS: 'Serbia', SL: 'Sierra Leone', SK: 'Slovakia', VN: 'Vietnam',
  SI: 'Slovenia', SO: 'Somalia', ZA: 'South Africa', ZW: 'Zimbabwe', ES: 'Spain',
  SS: 'S. Sudan', SD: 'Sudan', EH: 'W. Sahara', SR: 'Suriname', SZ: 'eSwatini',
  SE: 'Sweden', CH: 'Switzerland', SY: 'Syria', TJ: 'Tajikistan', TH: 'Thailand',
  TG: 'Togo', TT: 'Trinidad and Tobago', AE: 'United Arab Emirates', TN: 'Tunisia', TR: 'Turkey',
  TM: 'Turkmenistan', UG: 'Uganda', UA: 'Ukraine', MK: 'Macedonia', EG: 'Egypt',
  GB: 'United Kingdom', TZ: 'Tanzania', US: 'United States of America', BF: 'Burkina Faso', UY: 'Uruguay',
  UZ: 'Uzbekistan', VE: 'Venezuela', YE: 'Yemen', ZM: 'Zambia',
}
