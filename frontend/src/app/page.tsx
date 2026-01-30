import Link from 'next/link';

export default function Home() {
  return (
    <main id="main-content" className="flex min-h-screen flex-col items-center justify-center p-4 sm:p-8 text-gray-900 dark:text-gray-100">
      {/* Hero Section */}
      <article className="text-center max-w-3xl mx-auto animate-fade-in-up">
        <div className="mb-6" aria-hidden="true">
          <span className="text-6xl">🌿</span>
        </div>
        
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-gray-900 dark:text-gray-100 mb-4">
          Ayush Habba
        </h1>
        
        <p className="text-xl text-gray-600 dark:text-gray-300 mb-8">
          Discover your unique Ayurvedic constitution and receive personalized 
          wellness recommendations powered by Neuro-Symbolic AI.
        </p>
        
        {/* Dosha Preview */}
        <section aria-label="Three Doshas overview" className="flex flex-wrap justify-center gap-4 sm:gap-8 mb-10">
          <div className="text-center">
            <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-vata-100 dark:bg-vata-700/30 flex items-center justify-center mb-2" aria-hidden="true">
              <span className="text-xl sm:text-2xl">💨</span>
            </div>
            <span className="text-sm font-medium text-vata-700 dark:text-vata-100">Vata</span>
          </div>
          <div className="text-center">
            <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-pitta-100 dark:bg-pitta-700/30 flex items-center justify-center mb-2" aria-hidden="true">
              <span className="text-xl sm:text-2xl">🔥</span>
            </div>
            <span className="text-sm font-medium text-pitta-700 dark:text-pitta-100">Pitta</span>
          </div>
          <div className="text-center">
            <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-kapha-100 dark:bg-kapha-700/30 flex items-center justify-center mb-2" aria-hidden="true">
              <span className="text-xl sm:text-2xl">🌊</span>
            </div>
            <span className="text-sm font-medium text-kapha-700 dark:text-kapha-100">Kapha</span>
          </div>
        </section>
        
        {/* CTA Buttons */}
        <nav className="flex flex-col sm:flex-row gap-4 justify-center" aria-label="Primary navigation">
          <Link
            href="/assess"
            className="px-6 sm:px-8 py-3 sm:py-4 bg-ayurveda-gold text-white font-semibold rounded-xl hover:bg-amber-600 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900"
          >
            Take Prakriti Assessment
          </Link>
          <Link
            href="/dashboard"
            className="px-6 sm:px-8 py-3 sm:py-4 bg-white text-gray-700 dark:bg-gray-900 dark:text-gray-200 font-semibold rounded-xl border-2 border-gray-200 dark:border-gray-700 hover:border-ayurveda-gold transition-all hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900"
          >
            View Dashboard
          </Link>
        </nav>
      </article>
      
      {/* Features */}
      <section className="mt-16 sm:mt-20 grid sm:grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6 md:gap-8 max-w-5xl w-full px-4" aria-labelledby="features-heading">
        <h2 id="features-heading" className="sr-only">Features</h2>
        <article className="bg-white/80 dark:bg-gray-900/70 backdrop-blur p-5 sm:p-6 rounded-2xl shadow-sm transition-all hover:shadow-md hover:-translate-y-1">
          <div className="text-2xl sm:text-3xl mb-3" aria-hidden="true">🧬</div>
          <h3 className="font-semibold text-base sm:text-lg mb-2">Deterministic Assessment</h3>
          <p className="text-gray-600 dark:text-gray-300 text-sm">
            Clinically validated C-DAC Ayusoft methodology for accurate Prakriti determination.
          </p>
        </article>
        <article className="bg-white/80 dark:bg-gray-900/70 backdrop-blur p-5 sm:p-6 rounded-2xl shadow-sm transition-all hover:shadow-md hover:-translate-y-1">
          <div className="text-2xl sm:text-3xl mb-3" aria-hidden="true">🤖</div>
          <h3 className="font-semibold text-base sm:text-lg mb-2">AI-Powered Plans</h3>
          <p className="text-gray-600 dark:text-gray-300 text-sm">
            Neuro-symbolic agents combine ancient wisdom with modern AI for personalized recommendations.
          </p>
        </article>
        <article className="bg-white/80 dark:bg-gray-900/70 backdrop-blur p-5 sm:p-6 rounded-2xl shadow-sm transition-all hover:shadow-md hover:-translate-y-1 sm:col-span-2 md:col-span-1">
          <div className="text-2xl sm:text-3xl mb-3" aria-hidden="true">🛡️</div>
          <h3 className="font-semibold text-base sm:text-lg mb-2">Safety First</h3>
          <p className="text-gray-600 dark:text-gray-300 text-sm">
            Built-in contraindication checking and safety reviews for every recommendation.
          </p>
        </article>
      </section>
      
      {/* Disclaimer */}
      <p className="mt-16 text-xs text-gray-400 dark:text-gray-500 text-center max-w-lg">
        This application provides wellness and educational information only. 
        It is not intended to diagnose, treat, cure, or prevent any disease. 
        Please consult a qualified healthcare practitioner.
      </p>
    </main>
  );
}
