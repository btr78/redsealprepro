import TradePrep from "./TradePrep";

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      name: "RedSeal Prep Pro",
      url: "https://www.redsealprep.pro",
    },
    {
      "@type": "SoftwareApplication",
      name: "RedSeal Prep Pro",
      applicationCategory: "EducationalApplication",
      operatingSystem: "Web",
      description:
        "Red Seal exam prep for 9 Canadian trades with 1,145+ practice questions, a timed exam simulator, and an AI tutor that explains every answer.",
      url: "https://www.redsealprep.pro",
      offers: [
        { "@type": "Offer", name: "Free", price: "0", priceCurrency: "CAD" },
        { "@type": "Offer", name: "Pro Monthly", price: "12", priceCurrency: "CAD" },
      ],
    },
  ],
};

export default function Home() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <TradePrep />
    </>
  );
}
