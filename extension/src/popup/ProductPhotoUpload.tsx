import {Image as ImageIcon} from "lucide-react";

export default function ProductPhotoUpload({
  file,
  onSelect,
  name,
  size,
  disabled = false,
}: {
  file: File | null;
  onSelect: (file: File | null) => void;
  name: string;
  size: number;
  disabled?: boolean;
}) {
  return (
    <section className="upload-box">
      <div className="upload-title">
        <strong>Product photo check</strong>
        <span>Upload photo to check for stock duplicates and visual edits.</span>
      </div>
      <label
        className={`video-drop ${disabled ? "disabled" : ""}`}
        onDragOver={e => e.preventDefault()}
        onDrop={e => {
          e.preventDefault();
          if (disabled) return;
          const f = e.dataTransfer.files[0];
          if (f) onSelect(f);
        }}
      >
        <ImageIcon size={15} />
        <span>Drop JPEG, PNG, or WebP here, or <b>browse files</b></span>
        <input
          disabled={disabled}
          type="file"
          accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
          onChange={e => {
            const f = e.target.files?.[0] || null;
            e.currentTarget.value = "";
            onSelect(f);
          }}
        />
      </label>
      <small className="video-guidance">Maximum 15 MB · Local perceptual hash and Gemma vision comparison.</small>
      {(file || name) && (
        <div className="video-selected">
          <span>{file?.name || name} · {(((file?.size || size) / 1048576).toFixed(2))} MB</span>
          <button type="button" onClick={() => onSelect(null)}>Remove / replace</button>
        </div>
      )}
    </section>
  );
}
