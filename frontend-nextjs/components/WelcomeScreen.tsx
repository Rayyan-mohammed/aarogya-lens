'use client';

interface WelcomeScreenProps {
  onSetQuery: (query: string) => void;
}

const WELCOME_CARDS = [
  {
    icon: '🍎',
    title: 'Child Nutrition',
    description: 'Stunting, wasting, underweight rates across 706 districts',
    query: 'Which 10 districts have the worst stunting rate nationally?',
  },
  {
    icon: '🩸',
    title: 'Anaemia Burden',
    description: 'Anaemia prevalence in children, pregnant & non-pregnant women',
    query: 'Compare anaemia rates in women across all states',
  },
  {
    icon: '🤱',
    title: 'Maternal Health',
    description: 'Institutional delivery, ANC visits, skilled birth attendance',
    query: 'Which districts have the lowest institutional delivery rates?',
  },
  {
    icon: '💉',
    title: 'Vaccination',
    description: 'Full immunisation rates: BCG, DPT, polio, measles by district',
    query: 'Show vaccination coverage across all districts',
  },
  {
    icon: '🔗',
    title: 'Correlations',
    description: 'Explore relationships between sanitation, nutrition, and health outcomes',
    query: 'Is open defecation correlated with child stunting at district level?',
  },
  {
    icon: '👩',
    title: 'Women\'s Health',
    description: 'Literacy, child marriage, empowerment, and reproductive health',
    query: 'Which districts in Uttar Pradesh have the highest child marriage rates?',
  },
];

export default function WelcomeScreen({ onSetQuery }: WelcomeScreenProps) {
  return (
    <div className="welcome">
      <div className="welcome-hero">
        <div className="welcome-icon">🏥</div>
        <h1>
          India's Health Data,<br />
          <span>Now Accessible to All</span>
        </h1>
        <p>
          Ask natural language questions over NFHS-5 data covering 706 districts across India.
          Get instant analysis, charts, and grounded insights — no SQL or data science skills needed.
        </p>
      </div>
      <div className="welcome-cards">
        {WELCOME_CARDS.map((card, i) => (
          <div
            key={i}
            className="welcome-card"
            onClick={() => onSetQuery(card.query)}
          >
            <div className="welcome-card-icon">{card.icon}</div>
            <h4>{card.title}</h4>
            <p>{card.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}