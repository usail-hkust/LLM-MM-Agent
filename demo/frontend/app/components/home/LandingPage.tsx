"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Sparkles, 
  Zap, 
  Shield, 
  Globe, 
  Cpu, 
  ArrowRight, 
  Play,
  Github,
  ChevronRight,
  Layers,
  Terminal,
  Database
} from "lucide-react";
import { Button } from "@/components/ui/button";

// Feature Card Component
function FeatureCard({ 
  icon: Icon, 
  title, 
  description, 
  delay 
}: { 
  icon: any; 
  title: string; 
  description: string; 
  delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5 }}
      className="group p-6 bg-white rounded-2xl border border-slate-200 hover:border-blue-300 hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300"
    >
      <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
        <Icon className="w-6 h-6 text-white" />
      </div>
      <h3 className="text-lg font-bold text-slate-800 mb-2">{title}</h3>
      <p className="text-slate-600 text-sm leading-relaxed">{description}</p>
    </motion.div>
  );
}

// Animated Background
function AnimatedBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-50 via-white to-purple-50" />
      <motion.div
        className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-400/20 rounded-full blur-3xl"
        animate={{
          scale: [1, 1.2, 1],
          x: [0, 30, 0],
          y: [0, -30, 0],
        }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-400/20 rounded-full blur-3xl"
        animate={{
          scale: [1.2, 1, 1.2],
          x: [0, -30, 0],
          y: [0, 30, 0],
        }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", delay: 1 }}
      />
    </div>
  );
}

// Hero Section
function HeroSection({ onGetStarted }: { onGetStarted: () => void }) {
  return (
    <section className="relative min-h-screen flex items-center justify-center px-6 overflow-hidden">
      <AnimatedBackground />
      
      <div className="relative z-10 max-w-5xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          {/* Badge */}
          <motion.div
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-200 rounded-full text-blue-700 text-sm font-medium mb-8"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
          >
            <Sparkles className="w-4 h-4" />
            <span>AI-Powered Agent Framework</span>
          </motion.div>

          {/* Main Title */}
          <h1 className="text-5xl md:text-7xl font-bold text-slate-900 mb-6 leading-tight">
            Build Intelligent
            <span className="block bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
              Mathematical Modeling AI Agent System
            </span>
          </h1>

          {/* Subtitle */}
          <p className="text-xl text-slate-600 mb-10 max-w-2xl mx-auto leading-relaxed">
            MM-Agent is an intelligent system that fully automates the end-to-end mathematical modeling workflow, from problem analysis and model formulation to computational solving and professional report generation.
          </p>

          {/* CTA Buttons */}
          <motion.div
            className="flex flex-wrap justify-center gap-4"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Button
              onClick={onGetStarted}
              size="lg"
              className="h-12 px-8 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold rounded-xl shadow-lg shadow-blue-500/25 hover:shadow-xl hover:shadow-blue-500/30 transition-all"
            >
              <Play className="w-5 h-5 mr-2" />
              Get Started
              <ArrowRight className="w-5 h-5 ml-2" />
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="h-12 px-8 border-slate-300 hover:bg-slate-50 rounded-xl font-semibold"
              onClick={() => window.open("https://github.com/usail-hkust/LLM-MM-Agent", "_blank")}
            >
              <Github className="w-5 h-5 mr-2" />
              View on GitHub
            </Button>
          </motion.div>

          {/* Stats */}
          <motion.div
            className="flex justify-center gap-12 mt-16"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
          >
            {[
              { value: "2-Hour", label: "End-to-End Modeling" },
              { value: "Full-Process", label: "Automated Modeling" },
              { value: "Interactive", label: "Data Analysis Engine" },
            ].map((stat, i) => (
              <div key={i} className="text-center">
                <div className="text-3xl font-bold text-slate-900">{stat.value}</div>
                <div className="text-sm text-slate-500">{stat.label}</div>
              </div>
            ))}
          </motion.div>
        </motion.div>
      </div>

      {/* Scroll Indicator */}
      <motion.div
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
        animate={{ y: [0, 10, 0] }}
        transition={{ duration: 2, repeat: Infinity }}
      >
        <ChevronRight className="w-6 h-6 text-slate-400 rotate-90" />
      </motion.div>
    </section>
  );
}

// Features Section
function FeaturesSection() {
  const features = [
    {
      icon: Zap,
      title: "2-Hour End-to-End Modeling",
      description: "Complete mathematical modeling workflow from problem analysis to report generation in just 2 hours.",
    },
    {
      icon: Terminal,
      title: "Full-Process Automated Modeling",
      description: "Automatically handles problem analysis, model formulation, computational solving, and professional reporting.",
    },
    {
      icon: Globe,
      title: "One-Click Model Generation",
      description: "Generate complete mathematical models with a single click. No manual programming required.",
    },
    {
      icon: Database,
      title: "Professional Report Generation",
      description: "Automatically generate professional mathematical modeling reports with proper formatting and documentation.",
    },
    {
      icon: Shield,
      title: "Multi-Domain Support",
      description: "Supports various mathematical modeling domains including optimization, differential equations, and statistical analysis.",
    },
    {
      icon: Layers,
      title: "Interactive Workflow",
      description: "Visualize and interact with each step of the modeling process. Monitor progress in real-time.",
    },
  ];

  return (
    <section className="py-24 px-6 bg-white">
      <div className="max-w-6xl mx-auto">
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h2 className="text-4xl font-bold text-slate-900 mb-4">
            Key Features
          </h2>
          <p className="text-xl text-slate-600 max-w-2xl mx-auto">
            Everything you need for intelligent mathematical modeling.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <FeatureCard key={i} {...feature} delay={0.1 * i} />
          ))}
        </div>
      </div>
    </section>
  );
}

// Demo Preview Section
function DemoSection() {
  return (
    <section className="py-24 px-6 bg-slate-900">
      <div className="max-w-6xl mx-auto">
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h2 className="text-4xl font-bold text-white mb-4">
            See It In Action
          </h2>
          <p className="text-xl text-slate-400">
            Watch how agents collaborate to solve complex problems
          </p>
        </motion.div>

        <motion.div
          className="relative rounded-2xl overflow-hidden border border-slate-700 shadow-2xl"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-purple-500/10" />
          <div className="bg-slate-800 px-4 py-3 flex items-center gap-2 border-b border-slate-700">
            <div className="flex gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <div className="w-3 h-3 rounded-full bg-yellow-500" />
              <div className="w-3 h-3 rounded-full bg-green-500" />
            </div>
            <div className="flex-1 text-center text-sm text-slate-400 font-mono">
              mm-agent — Interactive Demo
            </div>
          </div>
          <div className="p-8 bg-slate-900 min-h-[400px] flex items-center justify-center">
            <div className="text-center">
              <Cpu className="w-16 h-16 text-blue-500 mx-auto mb-4" />
              <p className="text-slate-400">Interactive demo preview</p>
              <p className="text-slate-500 text-sm mt-2">
                Click "Get Started" to try it yourself
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// Footer
function Footer() {
  return (
    <footer className="bg-slate-900 border-t border-slate-800 py-12 px-6">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <span className="text-white font-semibold">MM Agent</span>
        </div>
        <p className="text-slate-500 text-sm">
          © 2026 MM Agent Framework. Open source under MIT License.
        </p>
      </div>
    </footer>
  );
}

// Main Landing Page
export default function LandingPage() {
  const router = useRouter();
  
  const handleGetStarted = () => {
    router.push("/login");
  };

  return (
    <div className="min-h-screen bg-white">
      <HeroSection onGetStarted={handleGetStarted} />
      <FeaturesSection />
      <DemoSection />
      <Footer />
    </div>
  );
}
