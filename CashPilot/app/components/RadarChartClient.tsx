"use client";
import dynamic from "next/dynamic";
const RadarChart = dynamic(() => import("./RadarChart"), { ssr: false });
export default RadarChart;
