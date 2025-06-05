import streamlit as st
import pandas as pd
import plotly.express as px
import chardet
import datetime
from io import BytesIO
import requests

# Konfigurasi awal dashboard
st.set_page_config(page_title="Dashboard Penjualan", layout="wide")

# Judul utama dan deskripsi
st.title("\U0001F4CA Dashboard Penjualan Interaktif untuk Toko & Bisnis Kecil")
st.markdown("Upload file penjualan (Excel/CSV), eksplorasi performa bisnis Anda, dan unduh data yang sudah dikonversi dan difilter.")

# Upload file oleh pengguna
uploaded = st.file_uploader("Upload file penjualan (.csv/.xlsx)", type=["csv", "xlsx"])

# Fungsi untuk mengambil kurs terbaru ke USD menggunakan exchangerate.host
@st.cache_data(ttl=3600)
def get_exchange_rates():
    # Ambil kunci API dari Streamlit Secrets
    api_key = st.secrets.get("EXCHANGE_RATE_API_KEY") # Gunakan .get untuk menghindari KeyError jika tidak ada
    if not api_key:
        st.error("Kunci API untuk Exchange Rate tidak ditemukan di Streamlit Secrets. Silakan tambahkan.")
        return {}

    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
    try:
        response = requests.get(url, timeout=10) # Tambah timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        if "conversion_rates" not in data:
            raise KeyError(f"'conversion_rates' key not found in response data: {data}")
        # Konversi dari USD ke mata uang lain (1 mata uang = X USD)
        # Jadi untuk 1 USD = Y mata uang, kita butuh 1 / Y USD
        # Ini berarti 1 IDR = Z USD, maka untuk mengkonversi Sales dari IDR ke USD adalah Sales * Z
        # API memberikan 1 USD = X IDR. Jadi 1 IDR = 1/X USD
        return {currency: 1 / rate for currency, rate in data["conversion_rates"].items() if rate != 0}
    except requests.exceptions.Timeout:
        st.error("Permintaan pengambilan kurs melebihi batas waktu. Coba lagi.")
        return {}
    except requests.exceptions.RequestException as e:
        st.error(f"Gagal terhubung ke API kurs: {e}. Silakan coba lagi nanti.")
        return {}
    except KeyError as e:
        st.error(f"Struktur data kurs tidak sesuai: {e}. Silakan hubungi pengembang.")
        return {}
    except Exception as e:
        st.error(f"Terjadi kesalahan tak terduga saat mengambil kurs: {e}")
        return {}

# Ambil kurs terbaru dari API
exchange_rates = get_exchange_rates()

if uploaded is not None and exchange_rates: # Pastikan exchange_rates tidak kosong
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
            st.warning("Kesalahan decoding terdeteksi. Berusaha membaca ulang dengan 'latin1'.")
    else:
        df = pd.read_excel(uploaded)

    required_columns = {"Order Date", "Sales"}
    if not required_columns.issubset(df.columns):
        st.error(f"File harus memiliki kolom wajib: **{', '.join(required_columns)}**")
        st.stop() # Hentikan eksekusi jika kolom wajib tidak ada
    else:
        df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")
        df["Sales"] = pd.to_numeric(df["Sales"], errors="coerce")
        df = df.dropna(subset=["Order Date", "Sales"])

        # Tambahkan pesan jika setelah dropna, data kosong
        if df.empty:
            st.warning("Tidak ada data yang valid setelah pembersihan kolom 'Order Date' dan 'Sales'. Pastikan format data benar.")
            st.stop()

        st.sidebar.header("\U0001F50D Filter Data")
        available_currencies = sorted(list(exchange_rates.keys()))

        # Pastikan 'IDR' ada dalam available_currencies sebelum mencoba menggunakannya sebagai index default
        default_currency_index = 0
        if "IDR" in available_currencies:
            default_currency_index = available_currencies.index("IDR")
        elif "USD" in available_currencies: # Fallback ke USD jika IDR tidak ada
            default_currency_index = available_currencies.index("USD")

        original_currency = st.sidebar.selectbox(
            "Mata Uang Asal Data Penjualan",
            options=available_currencies,
            index=default_currency_index
        )

        exchange_rate = exchange_rates.get(original_currency, 1.0)
        st.sidebar.markdown(f"**Kurs Real-time**: 1 {original_currency} = **{exchange_rate:.6f} USD**")

        df["Sales_USD"] = df["Sales"] * exchange_rate

        # Pastikan min_date dan max_date ada setelah filtering dan dropna
        if not df.empty:
            min_date = df["Order Date"].min().date()
            max_date = df["Order Date"].max().date()
            date_range = st.sidebar.date_input("Rentang Tanggal", [min_date, max_date])
            if len(date_range) == 2:
                start_date = datetime.datetime.combine(date_range[0], datetime.datetime.min.time())
                end_date = datetime.datetime.combine(date_range[1], datetime.datetime.max.time())
                df = df[(df["Order Date"] >= start_date) & (df["Order Date"] <= end_date)]
        else:
            st.info("Tidak ada data untuk difilter berdasarkan tanggal setelah pembersihan data awal.")
            st.stop()


        if "Category" in df.columns and not df["Category"].dropna().empty:
            categories = df["Category"].dropna().unique().tolist()
            selected_categories = st.sidebar.multiselect(
                "Kategori Produk",
                categories,
                default=categories if categories else [] # Pastikan default tidak None jika categories kosong
            )
            df = df[df["Category"].isin(selected_categories)]
        elif "Category" not in df.columns:
            st.sidebar.info("Kolom 'Category' tidak ditemukan. Filter kategori tidak tersedia.")

        if "Region" in df.columns and not df["Region"].dropna().empty:
            regions = df["Region"].dropna().unique().tolist()
            selected_regions = st.sidebar.multiselect(
                "Wilayah",
                regions,
                default=regions if regions else [] # Pastikan default tidak None jika regions kosong
            )
            df = df[df["Region"].isin(selected_regions)]
        elif "Region" not in df.columns:
            st.sidebar.info("Kolom 'Region' tidak ditemukan. Filter wilayah tidak tersedia.")

        # Re-check if dataframe is empty after all filters
        if df.empty:
            st.warning("Tidak ada data yang tersisa setelah menerapkan filter. Silakan sesuaikan filter Anda.")
            st.stop() # Hentikan eksekusi lebih lanjut jika dataframe kosong

        st.subheader("\U0001F4C4 Sample Data Terfilter")
        st.dataframe(df.head())

        st.subheader("\U0001F4C8 Ringkasan Penjualan (USD)")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Penjualan", f"${df['Sales_USD'].sum():,.2f}")
        col2.metric("Rata-rata per Order", f"${df['Sales_USD'].mean():,.2f}")
        col3.metric("Jumlah Order", f"{len(df):,}")
        st.caption(f"*Data dikonversi dari **{original_currency}** menggunakan kurs real-time dari exchangerate.host*")

        df_monthly = df.resample('M', on='Order Date').sum(numeric_only=True).reset_index()

        st.subheader("\U0001F4C6 Penjualan Bulanan (USD)")
        fig_line = px.line(df_monthly, x="Order Date", y="Sales_USD", title="Total Penjualan Bulanan dalam USD", markers=True)
        fig_line.update_traces(line=dict(color='royalblue'), marker=dict(size=6))
        fig_line.update_layout(xaxis_title='Bulan', yaxis_title='Total Penjualan (USD)')

        # Validasi untuk menghindari error jika df_monthly kosong
        if not df_monthly.empty:
            last_month = df_monthly["Order Date"].max()
            if last_month.month == datetime.datetime.now().month and last_month.year == datetime.datetime.now().year:
                st.caption("⚠️ Data bulan berjalan mungkin belum final. Perbarui data di akhir bulan.")
        else:
            st.info("Tidak ada data penjualan bulanan untuk ditampilkan.")


        st.plotly_chart(fig_line, use_container_width=True)

        if "Category" in df.columns and not df["Category"].dropna().empty:
            st.subheader("\U0001F4E6 Penjualan per Kategori")
            cat_group = df.groupby("Category")["Sales_USD"].sum().sort_values(ascending=False).reset_index()
            fig_bar = px.bar(cat_group, x="Category", y="Sales_USD", color="Category", text_auto=".2s",
                             title="Total Penjualan per Kategori (USD)")
            fig_bar.update_traces(hovertemplate='Kategori: %{x}<br>Penjualan: $%{y:,.2f}')
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Tidak ada data kategori untuk menampilkan penjualan per kategori.")


        if "Region" in df.columns and not df["Region"].dropna().empty:
            st.subheader("\U0001F30E Distribusi Penjualan per Wilayah")
            region_group = df.groupby("Region")["Sales_USD"].sum().reset_index()
            fig_pie = px.pie(region_group, names="Region", values="Sales_USD", title="Persentase Penjualan per Wilayah", hole=0.4)
            fig_pie.update_traces(textinfo='label+percent+value')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Tidak ada data wilayah untuk menampilkan distribusi penjualan per wilayah.")


        st.subheader("\U0001F4E5 Unduh Data Terfilter (USD)")
        def convert_df_to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name="Penjualan")
            return output.getvalue()

        download_excel = convert_df_to_excel(df)
        st.download_button(
            label="\U0001F4E4 Unduh Data ke Excel",
            data=download_excel,
            file_name="data_penjualan_terfilter_usd.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

elif uploaded is None:
    st.info("\U0001F4C2 Silakan unggah file penjualan terlebih dahulu untuk memulai.")
elif not exchange_rates: # Pesan ini hanya akan muncul jika get_exchange_rates gagal dan mengembalikan {}
    st.error("Dashboard tidak dapat menampilkan data kurs. Pastikan koneksi internet stabil atau kunci API valid.")