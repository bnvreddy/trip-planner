import { Map, Loader2 } from "lucide-react";

export default function KeywordSelector({ tripData, availableKeywords, onToggle, onBack, onGenerate, loading }) {
  return (
    <div className="max-w-3xl mx-auto">
      <button onClick={onBack} className="text-sm text-blue-600 font-medium mb-4 hover:underline">&larr; Back to details</button>
      <h2 className="text-3xl font-bold mb-2">Curate your {tripData.destination_city} experience</h2>
      <p className="text-gray-500 mb-8">Select the types of places you want the AI to prioritize.</p>
      <div className="space-y-8">
        {Object.entries(availableKeywords).map(([category, keywords]) => (
          <div key={category} className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <h3 className="text-lg font-bold text-gray-800 mb-4">{category}</h3>
            <div className="flex flex-wrap gap-3">
              {keywords.map((kw) => {
                const isSelected = tripData.selected_keywords.includes(kw);
                return (
                  <button key={kw} onClick={() => onToggle(kw)} className={`px-4 py-2 rounded-full border text-sm font-medium transition-all ${isSelected ? "bg-blue-600 text-white border-blue-600 shadow-md" : "bg-gray-50 text-gray-700 border-gray-200 hover:border-blue-400 hover:bg-blue-50"}`}>
                    {kw}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <button onClick={onGenerate} disabled={loading} className="w-full mt-8 bg-black hover:bg-gray-800 text-white font-bold py-4 px-4 rounded-xl flex justify-center items-center gap-2 transition">
        {loading ? <Loader2 className="animate-spin w-5 h-5" /> : <Map className="w-5 h-5" />}
        {loading ? "AI is calculating optimal routes..." : "Generate Smart Itinerary"}
      </button>
    </div>
  );
}