import test from "node:test";
import assert from "node:assert/strict";
import { reactive, nextTick } from "vue";
import { useWorkbenchLiveEvents, MAX_LIVE_BUFFER } from "./composables/useWorkbenchLiveEvents.js";
import { useAttachmentPipeline, MAX_ATTACHMENTS } from "./composables/useAttachmentPipeline.js";

test("OPT-04: useWorkbenchLiveEvents membatasi buffer ke MAX_LIVE_BUFFER (500 entri)", async () => {
  const props = reactive({
    activityEvents: [],
    outputLines: null,
    problems: null,
    error: null,
  });

  const { localOutputLines, localProblems } = useWorkbenchLiveEvents(props);

  // Buat 550 event tool_called
  const dummyEvents = [];
  for (let i = 1; i <= 550; i++) {
    dummyEvents.push({
      event_type: "tool_called",
      payload: { tool: `tool_${i}`, path: `file_${i}.txt` },
      timestamp: i,
    });
  }

  props.activityEvents = dummyEvents;
  await nextTick();

  assert.equal(localOutputLines.value.length, MAX_LIVE_BUFFER);
  assert.equal(MAX_LIVE_BUFFER, 500);

  // Verifikasi circular buffer menyimpan 500 entri terakhir (index 51 sampai 550)
  assert.ok(localOutputLines.value[0].text.includes("tool_51"));
  assert.ok(localOutputLines.value[499].text.includes("tool_550"));
});

test("OPT-07: useAttachmentPipeline membatasi kuota attachment ke MAX_ATTACHMENTS (8 berkas)", () => {
  const pipeline = useAttachmentPipeline({ scopeLabel: "task" });
  assert.equal(pipeline.maxAttachments, MAX_ATTACHMENTS);
  assert.equal(pipeline.attachments.value.length, 0);

  // Simulasikan penambahan 10 file sekaligus
  const dummyFiles = Array.from({ length: 10 }, (_, i) => ({
    name: `image_${i}.png`,
    type: "image/png",
  }));

  // Global mock FileReader jika berjalan di runtime Node.js
  globalThis.FileReader = class {
    readAsDataURL(file) {
      this.result = `data:${file.type};base64,ZmFrZQ==`;
      if (typeof this.onload === "function") this.onload();
    }
  };

  pipeline.onFilesPicked({ target: { files: dummyFiles } });

  // Harus tepat 8 file
  assert.equal(pipeline.attachments.value.length, 8);
  assert.ok(pipeline.attachError.value.includes("Hanya 8 gambar pertama"));

  // Operasi remove attachment
  pipeline.removeAttachment(0);
  assert.equal(pipeline.attachments.value.length, 7);

  // Operasi clear attachments
  pipeline.clearAttachments();
  assert.equal(pipeline.attachments.value.length, 0);
  assert.equal(pipeline.attachError.value, "");

  // Operasi restore attachments
  pipeline.restoreAttachments([{ name: "restored.jpg", base64: "123" }]);
  assert.equal(pipeline.attachments.value.length, 1);
  assert.equal(pipeline.attachments.value[0].name, "restored.jpg");
});

test("OPT-07: useAttachmentPipeline menolak tipe MIME yang tidak diizinkan", () => {
  const pipeline = useAttachmentPipeline();

  const invalidFiles = [
    { name: "script.sh", type: "text/x-sh" },
    { name: "document.pdf", type: "application/pdf" },
  ];

  pipeline.onFilesPicked({ target: { files: invalidFiles } });

  assert.equal(pipeline.attachments.value.length, 0);
  assert.ok(pipeline.attachError.value.includes("Format tidak didukung"));
});
