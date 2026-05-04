"use client";
import { AtomShell } from "./AtomShell";
import { Database, ChevronRight, ChevronDown } from "lucide-react";
import { useState } from "react";
import { RenderAtomProps } from "@/app/domain/abp";

const Node = ({ name, value, depth = 0 }: any) => {
  const [open, setOpen] = useState(depth < 2);
  const isObj = value && typeof value === 'object';
  if (!isObj) return <div className="flex gap-2 text-xs pl-4 font-mono"><span className="text-slate-500">{name}:</span><span className="text-emerald-600 break-all">{String(value)}</span></div>;
  return (
    <div className="pl-2 font-mono text-xs">
      <div className="flex items-center gap-1 cursor-pointer hover:bg-slate-100 rounded px-1 select-none" onClick={(e) => { e.stopPropagation(); setOpen(!open); }}>
        {open ? <ChevronDown className="w-3 h-3 text-slate-400"/> : <ChevronRight className="w-3 h-3 text-slate-400"/>}
        <span className="font-bold text-purple-700">{name}</span>
        <span className="text-slate-400 text-[10px]">{Array.isArray(value) ? `[${value.length}]` : '{...}'}</span>
      </div>
      {open && <div className="border-l border-slate-200 ml-1.5">{Object.entries(value).map(([k,v]) => <Node key={k} name={k} value={v} depth={depth+1}/>)}</div>}
    </div>
  );
};

export function AtomData(props: RenderAtomProps) {
  const { block } = props;
  return (
    <AtomShell
      {...props}
      label="Data Explorer"
      icon={Database}
      contentToCopy={JSON.stringify(block.content, null, 2)}
    >
      <div className="p-4 bg-white overflow-auto max-h-[400px]">
        <Node name="root" value={block.content} />
      </div>
    </AtomShell>
  );
}
