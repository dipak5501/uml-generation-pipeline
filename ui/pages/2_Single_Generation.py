import streamlit as st

from ui.api_client import api_get, api_get_bytes, api_post

st.set_page_config(page_title="Single Generation", layout="wide")
st.title("Single Generation")

requirement = st.text_area(
    "Software requirement / feature / user story",
    height=140,
    placeholder="As a shopper, I want to add books to a cart and checkout with saved payment methods...",
)
diagram_type = st.selectbox("Diagram type", ["class", "object", "component", "package"])
run = st.button("Generate", type="primary", disabled=not requirement.strip())

if run:
    with st.spinner("Generating specification, PlantUML, render, and scores..."):
        try:
            result = api_post(
                "/api/generate",
                {"requirement": requirement.strip(), "diagram_type": diagram_type},
            )
            st.session_state["last_artifact"] = result["artifact"]
            st.success(f"Created artifact #{result['artifact']['id']} (job {result['job_id']})")
        except Exception as exc:
            st.error(f"Generation failed: {exc}")

artifact = st.session_state.get("last_artifact")
if artifact:
    st.subheader("Trace")
    st.markdown("**Requirement**")
    st.write(artifact["source_requirement"])
    st.markdown("**Technical specification**")
    st.text(artifact["technical_spec"])
    st.markdown("**PlantUML**")
    st.code(artifact["plantuml_code"], language="text")
    st.download_button("Download PlantUML", artifact["plantuml_code"], file_name="diagram.puml")

    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"**Render status:** `{artifact['render_status']}`")
        st.metric("Final weighted score", f"{artifact['composite_score']:.3f}")
        if artifact.get("validation_messages"):
            st.warning(artifact["validation_messages"])
    with cols[1]:
        if artifact["render_status"] == "success":
            try:
                img = api_get_bytes(f"/api/artifacts/{artifact['id']}/image")
                st.image(img, caption="Rendered diagram")
                st.download_button("Download image", img, file_name=f"diagram.{artifact.get('image_format','png')}")
            except Exception as exc:
                st.error(f"Image load failed: {exc}")
        else:
            st.error("Render failed — composite score set to 0. Use Repair or check Settings.")

    st.subheader("Model scores")
    st.dataframe(artifact.get("model_scores") or [], use_container_width=True)

    if artifact.get("repair_attempts"):
        st.subheader("Repair attempts")
        st.dataframe(artifact["repair_attempts"], use_container_width=True)
