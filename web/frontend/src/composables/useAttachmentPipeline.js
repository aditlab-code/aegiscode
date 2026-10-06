/**
 * useAttachmentPipeline.js
 *
 * Mengisolasi penanganan pipeline attachment multimodal (JPEG/PNG/WebP),
 * validasi kuota batas berkas, pembacaan base64 FileReader, dan manipulasi antrean gambar.
 */
import { ref } from "vue";

export const MAX_ATTACHMENTS = 8;
export const ACCEPTED_ATTACHMENT_TYPES = ["image/jpeg", "image/png", "image/webp"];

export function useAttachmentPipeline(options = {}) {
  const maxAttachments = options.maxAttachments || MAX_ATTACHMENTS;
  const acceptedTypes = options.acceptedTypes || ACCEPTED_ATTACHMENT_TYPES;
  const scopeLabel = options.scopeLabel || "pesan";

  const attachments = ref([]);
  const attachError = ref("");

  function clearAttachments() {
    attachments.value = [];
    attachError.value = "";
  }

  function removeAttachment(index) {
    if (index >= 0 && index < attachments.value.length) {
      attachments.value.splice(index, 1);
    }
  }

  function restoreAttachments(items) {
    if (Array.isArray(items)) {
      attachments.value = items.slice(0, maxAttachments);
    }
  }

  function triggerAttach(fileInputEl, isDisabled = false) {
    if (isDisabled) return;
    if (fileInputEl && typeof fileInputEl.click === "function") {
      fileInputEl.click();
    }
  }

  function onFilesPicked(e) {
    const rawFiles = e?.target?.files;
    const files = Array.from(rawFiles || []);
    if (e?.target) {
      e.target.value = "";
    }
    const remainingSlots = maxAttachments - attachments.value.length;
    if (remainingSlots <= 0) {
      attachError.value = `Maksimum ${maxAttachments} gambar per ${scopeLabel}.`;
      return;
    }
    const filesToProcess = files.slice(0, remainingSlots);
    if (files.length > remainingSlots) {
      attachError.value = `Hanya ${remainingSlots} gambar pertama yang ditambahkan (maksimum ${maxAttachments}).`;
    }
    for (const file of filesToProcess) {
      if (!acceptedTypes.includes(file.type)) {
        attachError.value = `Format tidak didukung: ${file.type || "unknown"} (pakai JPEG/PNG/WebP).`;
        continue;
      }
      if (typeof FileReader === "undefined") {
        continue;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = String(reader.result || "");
        const comma = dataUrl.indexOf(",");
        const base64 = comma >= 0 ? dataUrl.slice(comma + 1) : "";
        if (!base64) return;
        attachments.value.push({
          name: file.name || "image",
          mimeType: file.type,
          dataUrl,
          base64,
        });
      };
      reader.onerror = () => {
        attachError.value = `Gagal membaca gambar: ${file.name || "unknown"}`;
      };
      reader.readAsDataURL(file);
    }
  }

  return {
    attachments,
    attachError,
    clearAttachments,
    removeAttachment,
    restoreAttachments,
    triggerAttach,
    onFilesPicked,
    maxAttachments,
    acceptedTypes,
  };
}
