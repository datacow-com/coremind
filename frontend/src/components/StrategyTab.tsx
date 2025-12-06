import { z } from "zod";
import { useFormZod } from "@/hooks/useFormZod";
import { StrategyConfigData } from "@/components/StrategyConfig";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import Button from "@/components/ui/button";
import { useEffect } from "react";

interface Props {
  config: any;
  onUpdate: (cfg: any) => Promise<void>;
}

export function StrategyTab({ config, onUpdate }: Props) {
  const schema = z.object({
    ocr_provider: z.enum(['deepseek', 'qwen-vl', 'volc_engine', 'paddle', 'auto']),
    force_ocr: z.boolean(),
    chunking_mode: z.enum(['fixed', 'semantic', 'layout_aware', 'table_first']),
    chunk_size: z.number().int().min(128).max(4096),
    chunk_overlap: z.number().int().min(0).max(512),
    embedding_model: z.string(),
    enable_quantization: z.boolean(),
  });

  const form = useFormZod(
    schema,
    {
      ocr_provider: config.ocr_provider || 'auto',
      force_ocr: config.force_ocr || false,
      chunking_mode: config.chunking?.mode || 'fixed',
      chunk_size: config.chunking?.chunk_size || 512,
      chunk_overlap: config.chunking?.chunk_overlap || 50,
      embedding_model: config.embedding_model || 'BAAI/bge-m3',
      enable_quantization: config.enable_quantization ?? true,
    },
    async (v) => {
      const strategyConfig: StrategyConfigData = {
        ocr_provider: v.ocr_provider,
        force_ocr: v.force_ocr,
        chunking: {
          mode: v.chunking_mode,
          chunk_size: v.chunk_size,
          chunk_overlap: v.chunk_overlap,
        },
        embedding_model: v.embedding_model,
        embedding_batch_size: 64, // Fixed for now or advanced setting
        enable_quantization: v.enable_quantization,
      };
      // Wrap in strategy_config key if backend expects it nested or merge
      await onUpdate({ strategy_config: strategyConfig });
    }
  );

  // Sync from props if config changes externally
  useEffect(() => {
    if (config) {
        form.setValues({
            ocr_provider: config.strategy_config?.ocr_provider || config.ocr_provider || 'auto',
            force_ocr: config.strategy_config?.force_ocr || config.force_ocr || false,
            chunking_mode: config.strategy_config?.chunking?.mode || config.chunking?.mode || 'fixed',
            chunk_size: config.strategy_config?.chunking?.chunk_size || config.chunking?.chunk_size || 512,
            chunk_overlap: config.strategy_config?.chunking?.chunk_overlap || config.chunking?.chunk_overlap || 50,
            embedding_model: config.strategy_config?.embedding_model || config.embedding_model || 'BAAI/bge-m3',
            enable_quantization: config.strategy_config?.enable_quantization ?? config.enable_quantization ?? true,
        });
    }
  }, [config]);

  return (
    <form onSubmit={form.submit} className="space-y-6 p-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* OCR Settings */}
        <div className="space-y-4 border p-4 rounded bg-gray-50">
          <h3 className="font-medium text-gray-900">OCR / Vision</h3>
          
          <div className="space-y-2">
            <Label>OCR Provider</Label>
            <select
              {...form.register("ocr_provider")}
              className="w-full border rounded p-2 bg-white"
            >
              <option value="auto">Auto (Best Effort)</option>
              <option value="deepseek">DeepSeek (Cost Efficient)</option>
              <option value="qwen-vl">Qwen-VL (Layout Aware)</option>
              <option value="volc_engine">VolcEngine (Robust)</option>
              <option value="paddle">PaddleOCR (Local)</option>
            </select>
          </div>

          <div className="flex items-center justify-between">
            <Label>Force OCR</Label>
            <Switch
              checked={form.get("force_ocr")}
              onCheckedChange={(c) => form.setValue("force_ocr", c)}
            />
          </div>
        </div>

        {/* Chunking Settings */}
        <div className="space-y-4 border p-4 rounded bg-gray-50">
          <h3 className="font-medium text-gray-900">Chunking Strategy</h3>
          
          <div className="space-y-2">
            <Label>Mode</Label>
            <select
              {...form.register("chunking_mode")}
              className="w-full border rounded p-2 bg-white"
            >
              <option value="fixed">Fixed Size</option>
              <option value="semantic">Semantic (Markdown)</option>
              <option value="layout_aware">Layout Aware</option>
              <option value="table_first">Table First (Extract Tables)</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Size (tokens)</Label>
              <input
                type="number"
                {...form.register("chunk_size", { valueAsNumber: true })}
                className="w-full border rounded p-2"
              />
              {form.error("chunk_size") && <p className="text-red-500 text-xs">{form.error("chunk_size")}</p>}
            </div>
            <div className="space-y-2">
              <Label>Overlap</Label>
              <input
                type="number"
                {...form.register("chunk_overlap", { valueAsNumber: true })}
                className="w-full border rounded p-2"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Indexing Settings */}
      <div className="space-y-4 border p-4 rounded bg-gray-50">
        <h3 className="font-medium text-gray-900">Indexing & Model</h3>
        
        <div className="space-y-2">
          <Label>Embedding Model</Label>
          <input
            {...form.register("embedding_model")}
            className="w-full border rounded p-2"
            placeholder="BAAI/bge-m3"
          />
        </div>

        <div className="flex items-center justify-between">
          <Label>Enable Quantization (Binary/Scalar)</Label>
          <Switch
            checked={form.get("enable_quantization")}
            onCheckedChange={(c) => form.setValue("enable_quantization", c)}
          />
        </div>
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={form.busy}>
          {form.busy ? "Saving..." : "Save Configuration"}
        </Button>
      </div>
    </form>
  );
}

