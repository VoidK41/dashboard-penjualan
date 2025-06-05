
import streamlit as st
import pandas as pd
import plotly.express as px
import chardet
import datetime
from io import BytesIO

st.set_page_config(page_title="Dashboard Penjualan", layout="wide")

st.title("📊 Dashboard Penjualan Interaktif untuk Toko & Bisnis Kecil")
st.markdown("Upload file penjualan (Excel/CSV), eksplorasi performa bisnis Anda, dan unduh data yang sudah difilter.")

uploaded = st.file_uploader("Upload file penjualan (.csv/.xlsx)", type=["csv", "xlsx"])

if uploaded is not None:
    if uploaded.name.endswith(".csv"):
        rawdata = uploaded.read()
        result = chardet.detect(rawdata)
        encoding = result['encoding']
        uploaded.seek(0)
        try:
            df = pd.read_csv(uploaded, encoding=encoding)
        except UnicodeDecodeError:
            uploaded.seek(0)
            df = pd.read_csv(uploaded, encoding='latin1')
            st.warning("Kesalahan decoding terdeteksi. Dibaca ulang dengan 'latin1'.")
    else:
        df = pd.read_excel(uploaded)

    required_columns = {"Order Date", "Sales"}
    if not required_columns.issubset(df.columns):
        st.error(f"File harus memiliki kolom: {', '.join(required_columns)}")
        st.stop()

    df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")
    df["Sales"] = pd.to_numeric(df["Sales"], errors="coerce")
    df = df.dropna(subset=["Order Date", "Sales"])

    if df.empty:
        st.warning("Data kosong setelah pembersihan. Pastikan format data Anda benar.")
        st.stop()

    st.sidebar.header("🔍 Filter Data")
    min_date = df["Order Date"].min().date()
    max_date = df["Order Date"].max().date()
    date_range = st.sidebar.date_input("Rentang Tanggal", [min_date, max_date])

    if len(date_range) == 2:
        start_date = datetime.datetime.combine(date_range[0], datetime.datetime.min.time())
        end_date = datetime.datetime.combine(date_range[1], datetime.datetime.max.time())
        df = df[(df["Order Date"] >= start_date) & (df["Order Date"] <= end_date)]

    if "Category" in df.columns:
        categories = df["Category"].dropna().unique().tolist()
        selected_categories = st.sidebar.multiselect("Kategori Produk", categories, default=categories)
        df = df[df["Category"].isin(selected_categories)]

    if "Region" in df.columns:
        regions = df["Region"].dropna().unique().tolist()
        selected_regions = st.sidebar.multiselect("Wilayah", regions, default=regions)
        df = df[df["Region"].isin(selected_regions)]

    if df.empty:
        st.warning("Data kosong setelah filter. Silakan sesuaikan filter.")
        st.stop()

    st.subheader("📄 Sample Data")
    st.dataframe(df.head())

    st.subheader("📊 Ringkasan Penjualan")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Penjualan", f"{df['Sales'].sum():,.2f}")
    col2.metric("Rata-rata per Order", f"{df['Sales'].mean():,.2f}")
    col3.metric("Jumlah Order", f"{len(df):,}")

    # Penjualan Bulanan
    df_monthly = df.resample('M', on='Order Date').sum(numeric_only=True).reset_index()

    st.subheader("📆 Penjualan Bulanan")
    fig_line = px.line(df_monthly, x="Order Date", y="Sales", title="Total Penjualan Bulanan", markers=True)
    st.plotly_chart(fig_line, use_container_width=True)

    # Tambahkan peringatan jika bulan berjalan belum final
    if not df_monthly.empty:
        last_month = df_monthly["Order Date"].max()
        now = datetime.datetime.now()
        if last_month.month == now.month and last_month.year == now.year:
            st.caption("⚠️ Data bulan berjalan mungkin belum final. Perbarui data di akhir bulan.")

    # Penjualan per Kategori
    if "Category" in df.columns:
        st.subheader("📦 Penjualan per Kategori")
        cat_group = df.groupby("Category")["Sales"].sum().sort_values(ascending=False).reset_index()
        fig_bar = px.bar(cat_group, x="Category", y="Sales", color="Category", text_auto=".2s")
        st.plotly_chart(fig_bar, use_container_width=True)

    # Penjualan per Wilayah
    if "Region" in df.columns:
        st.subheader("🗺️ Distribusi Penjualan per Wilayah")
        region_group = df.groupby("Region")["Sales"].sum().reset_index()
        fig_pie = px.pie(region_group, names="Region", values="Sales", hole=0.4)
        fig_pie.update_traces(textinfo='label+percent+value')
        st.plotly_chart(fig_pie, use_container_width=True)

    # Unduh Excel
    st.subheader("📥 Unduh Data Terfilter")
    def convert_df_to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Penjualan")
        return output.getvalue()

    download_excel = convert_df_to_excel(df)
    st.download_button(
        label="📤 Unduh Data ke Excel",
        data=download_excel,
        file_name="data_penjualan_terfilter.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("📂 Silakan unggah file penjualan terlebih dahulu untuk memulai.")
