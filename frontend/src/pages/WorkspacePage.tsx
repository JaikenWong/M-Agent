import { useEffect, useState } from "react";
import { api } from "@/api/endpoints";
import type { WorkspaceEntry, FileContent } from "@/types";
import { File, Folder, FolderOpen, ChevronRight } from "lucide-react";

interface TreeNode {
  name: string;
  path: string;
  isDir: boolean;
  children: TreeNode[];
}

function buildTree(entries: WorkspaceEntry[]): TreeNode[] {
  const root: TreeNode[] = [];
  const map = new Map<string, TreeNode>();

  for (const e of entries) {
    const node: TreeNode = { name: e.path.split("/").pop()!, path: e.path, isDir: e.is_dir, children: [] };
    map.set(e.path, node);
  }

  for (const e of entries) {
    const parts = e.path.split("/");
    if (parts.length === 1) {
      root.push(map.get(e.path)!);
    } else {
      const parentPath = parts.slice(0, -1).join("/");
      const parent = map.get(parentPath);
      if (parent) parent.children.push(map.get(e.path)!);
      else root.push(map.get(e.path)!);
    }
  }
  return root;
}

function TreeItem({ node, depth, onSelect }: { node: TreeNode; depth: number; onSelect: (path: string) => void }) {
  const [expanded, setExpanded] = useState(depth < 2);
  return (
    <div>
      <button
        onClick={() => node.isDir ? setExpanded(!expanded) : onSelect(node.path)}
        className="flex items-center gap-1.5 w-full py-0.5 px-1 text-sm text-gray-300 hover:bg-gray-800 rounded"
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
      >
        {node.isDir ? (
          expanded ? <FolderOpen size={14} className="text-yellow-400" /> : <Folder size={14} className="text-yellow-400" />
        ) : (
          <File size={14} className="text-gray-500" />
        )}
        <span className="truncate">{node.name}</span>
        {node.isDir && <ChevronRight size={12} className={`ml-auto transition-transform ${expanded ? "rotate-90" : ""}`} />}
      </button>
      {expanded && node.children.map((child) => (
        <TreeItem key={child.path} node={child} depth={depth + 1} onSelect={onSelect} />
      ))}
    </div>
  );
}

export function WorkspacePage() {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [file, setFile] = useState<FileContent | null>(null);

  useEffect(() => {
    api.getWorkspaceTree().then((data) => setTree(buildTree(data.entries))).catch(() => {});
  }, []);

  const handleSelect = (path: string) => {
    api.getWorkspaceFile(path).then(setFile).catch(() => setFile(null));
  };

  return (
    <div className="flex h-full">
      <div className="w-64 border-r border-gray-800 overflow-y-auto p-2">
        {tree.length === 0 ? (
          <div className="text-xs text-gray-600 p-2">工作区为空</div>
        ) : (
          tree.map((n) => <TreeItem key={n.path} node={n} depth={0} onSelect={handleSelect} />)
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {file ? (
          <>
            <div className="text-xs text-gray-500 mb-2">{file.path}</div>
            <pre className="text-sm text-gray-300 bg-bg-panel rounded-lg p-4 overflow-x-auto whitespace-pre-wrap font-mono">
              {file.content}
            </pre>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-600 text-sm">
            选择文件查看内容
          </div>
        )}
      </div>
    </div>
  );
}
