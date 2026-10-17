from agent.adapters.images.shared import page_images

SETTINGS = {
    "render_dpi": 144,
    "max_image_px": 440,
    "max_upscale": 4.0,
    "ruler_step_px": 100,
    "crop_max_px": 500,
    "cache_size": 2,
    "scan_min_coverage": 0.8,
}


def test_same_settings_share_one_instance(tmp_path):
    documents = [{"id": "plan", "path": "plan.pdf", "legal_force": "conformity"}]
    first = page_images(documents=documents, root=tmp_path, **SETTINGS)
    again = page_images(documents=[{"id": "plan", "path": "plan.pdf"}], root=tmp_path, **SETTINGS)
    assert again is first
    other = page_images(documents=documents, root=tmp_path, **{**SETTINGS, "render_dpi": 72})
    assert other is not first
    assert page_images(documents=documents, root=tmp_path / "x", **SETTINGS) is not first
