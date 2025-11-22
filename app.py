"""
PrimeTrade.ai - Bitcoin Trader Sentiment Analysis Dashboard
===========================================================
Interactive Streamlit dashboard for exploring trader performance
and market sentiment relationships.

Author: Navneet Shukla
Date: November 2025
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="PrimeTrade.ai - Trader Sentiment Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    h1 {
        color: #1f77b4;
        padding-bottom: 20px;
    }
    h2 {
        color: #2c3e50;
        padding-top: 20px;
        padding-bottom: 10px;
    }
    .highlight {
        background-color: #ffffcc;
        padding: 10px;
        border-left: 5px solid #ff6b6b;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)


# ============================================================
# DATA LOADING (WITH CACHING)
# ============================================================

@st.cache_data
def load_data():
    """Load and preprocess all data"""
    
    # Load raw data
    df_trader = pd.read_csv('data/historical_data.csv')
    df_sentiment = pd.read_csv('data/fear_greed_index.csv')
    
    # Drop unnecessary columns
    columns_to_drop = ['Transaction Hash', 'Order ID', 'Trade ID', 'Timestamp']
    df_trader.drop(columns=columns_to_drop, inplace=True, errors='ignore')
    
    # Convert timestamps
    df_trader['Timestamp IST'] = pd.to_datetime(df_trader['Timestamp IST'], dayfirst=True, errors='coerce')
    df_sentiment['timestamp'] = pd.to_datetime(df_sentiment['timestamp'])
    df_sentiment['date'] = pd.to_datetime(df_sentiment['date'])
    
    # Create date columns
    df_trader['date'] = pd.to_datetime(df_trader['Timestamp IST'].dt.date)
    df_sentiment['date'] = pd.to_datetime(df_sentiment['date'].dt.date)
    
    # Merge datasets
    df_merged = df_trader.merge(
        df_sentiment[['date', 'value', 'classification']],
        on='date',
        how='left'
    )
    df_merged = df_merged.dropna(subset=['value', 'classification'])
    
    # Feature engineering
    df_merged['is_profitable'] = df_merged['Closed PnL'] > 0
    df_merged['roi'] = (df_merged['Closed PnL'] / df_merged['Size USD']) * 100
    df_merged['net_pnl'] = df_merged['Closed PnL'] - df_merged['Fee']
    
    # Remove infinite ROI values
    df_merged = df_merged[~np.isinf(df_merged['roi'])]
    
    # Position type
    def classify_direction(x):
        x = str(x)
        if 'Short' in x and 'Long' in x:
            return 'Other'
        elif 'Short' in x:
            return 'Short'
        elif 'Long' in x:
            return 'Long'
        else:
            return 'Other'
    
    df_merged['position_type'] = df_merged['Direction'].apply(classify_direction)
    
    # Sentiment categories
    df_merged['sentiment_category'] = pd.cut(
        df_merged['value'],
        bins=[-float('inf'), 30, 45, 55, 70, float('inf')],
        labels=['Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed'],
        right=False
    )
    
    # Time features
    df_merged['hour'] = df_merged['Timestamp IST'].dt.hour
    df_merged['day_of_week'] = df_merged['Timestamp IST'].dt.day_name()
    df_merged['month'] = df_merged['Timestamp IST'].dt.month
    
    # Trader features
    trader_stats = df_merged.groupby('Account').agg({
        'Closed PnL': 'sum',
        'Account': 'size',
        'is_profitable': 'mean'
    })
    trader_stats.columns = ['total_pnl', 'total_trades', 'win_rate']
    
    df_merged = df_merged.merge(
        trader_stats,
        left_on='Account',
        right_index=True,
        suffixes=('', '_trader')
    )
    
    return df_merged

# Load data
with st.spinner('🔄 Loading data...'):
    df = load_data()

# ============================================================
# SIDEBAR - FILTERS
# ============================================================

st.sidebar.title("🎛️ Dashboard Filters")
st.sidebar.markdown("---")

# Date range filter
st.sidebar.subheader("📅 Date Range")
min_date = df['date'].min().date()
max_date = df['date'].max().date()
date_range = st.sidebar.date_input(
    "Select period",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Sentiment filter
st.sidebar.subheader("😨 Market Sentiment")
sentiment_options = st.sidebar.multiselect(
    "Select sentiment(s)",
    options=['Fear', 'Greed'],
    default=['Fear', 'Greed']
)

# Coin filter
st.sidebar.subheader("🪙 Cryptocurrency")
top_coins = df['Coin'].value_counts().head(10).index.tolist()
selected_coins = st.sidebar.multiselect(
    "Select coin(s)",
    options=['All'] + top_coins,
    default=['All']
)

# Position type filter
st.sidebar.subheader("📈 Position Type")
position_filter = st.sidebar.multiselect(
    "Select position(s)",
    options=['Long', 'Short', 'Other'],
    default=['Long', 'Short']
)

# Apply filters
df_filtered = df.copy()

# Date filter
if len(date_range) == 2:
    df_filtered = df_filtered[
        (df_filtered['date'] >= pd.to_datetime(date_range[0])) &
        (df_filtered['date'] <= pd.to_datetime(date_range[1]))
    ]

# Sentiment filter
if sentiment_options:
    df_filtered = df_filtered[df_filtered['classification'].isin(sentiment_options)]

# Coin filter
if 'All' not in selected_coins and selected_coins:
    df_filtered = df_filtered[df_filtered['Coin'].isin(selected_coins)]

# Position filter
if position_filter:
    df_filtered = df_filtered[df_filtered['position_type'].isin(position_filter)]

st.sidebar.markdown("---")
st.sidebar.info(f"📊 **{len(df_filtered):,}** trades selected\n\n👥 **{df_filtered['Account'].nunique():,}** unique traders")


# ============================================================
# MAIN DASHBOARD
# ============================================================

# Header
st.title("📊 Bitcoin Trader Sentiment Analysis Dashboard")
st.markdown("### *Exploring the relationship between trader performance and market sentiment*")
st.markdown("---")

# ============================================================
# KEY METRICS ROW
# ============================================================

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    total_trades = len(df_filtered)
    st.metric(
        label="🔢 Total Trades",
        value=f"{total_trades:,}",
        delta=f"{(total_trades/len(df)*100):.1f}% of dataset"
    )

with col2:
    total_pnl = df_filtered['Closed PnL'].sum()
    st.metric(
        label="💰 Total PnL",
        value=f"${total_pnl:,.0f}",
        delta=f"${df_filtered['Closed PnL'].mean():.2f} avg"
    )

with col3:
    win_rate = df_filtered['is_profitable'].mean() * 100
    st.metric(
        label="🎯 Win Rate",
        value=f"{win_rate:.1f}%",
        delta=f"{win_rate - 50:.1f}% vs 50%"
    )

with col4:
    avg_roi = df_filtered['roi'].mean()
    st.metric(
        label="📈 Avg ROI",
        value=f"{avg_roi:.2f}%",
        delta="Per trade"
    )

with col5:
    unique_traders = df_filtered['Account'].nunique()
    st.metric(
        label="👥 Active Traders",
        value=f"{unique_traders:,}",
        delta=f"{unique_traders/df['Account'].nunique()*100:.1f}%"
    )

st.markdown("---")

# ============================================================
# TAB NAVIGATION
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview", 
    "😨 Sentiment Analysis", 
    "🏆 Trader Insights",
    "🪙 Coin Performance",
    "⏰ Time Patterns"
])

# ============================================================
# TAB 1: OVERVIEW
# ============================================================

with tab1:
    st.header("📊 Market Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # PnL Distribution
        fig = go.Figure()
        for sentiment in df_filtered['classification'].unique():
            data = df_filtered[df_filtered['classification'] == sentiment]['Closed PnL']
            fig.add_trace(go.Box(
                y=data,
                name=sentiment,
                marker_color='red' if sentiment == 'Fear' else 'green'
            ))
        
        fig.update_layout(
            title="PnL Distribution by Sentiment",
            yaxis_title="Closed PnL ($)",
            showlegend=True,
            height=400
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Trade Volume Over Time
        daily_trades = df_filtered.groupby(['date', 'classification']).size().reset_index(name='count')
        fig = px.area(
            daily_trades,
            x='date',
            y='count',
            color='classification',
            title="Trading Volume Over Time",
            color_discrete_map={'Fear': '#d32f2f', 'Greed': '#388e3c'}
        )
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Number of Trades",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Performance Summary Table
    st.subheader("📋 Performance Summary")
    
    summary = df_filtered.groupby('classification').agg({
        'Closed PnL': ['mean', 'sum', 'std'],
        'is_profitable': 'mean',
        'roi': 'mean',
        'Size USD': 'mean',
        'Account': 'count'
    }).round(2)
    
    summary.columns = ['Avg PnL', 'Total PnL', 'PnL StdDev', 'Win Rate', 'Avg ROI', 'Avg Size', 'Trade Count']
    summary['Win Rate'] = (summary['Win Rate'] * 100).round(1).astype(str) + '%'
    
    st.dataframe(summary, use_container_width=True)

# ============================================================
# TAB 2: SENTIMENT ANALYSIS
# ============================================================

with tab2:
    st.header("😨 Fear vs Greed Analysis")
    
    # Key Insight Box
    fear_pnl = df_filtered[df_filtered['classification'] == 'Fear']['Closed PnL'].mean()
    greed_pnl = df_filtered[df_filtered['classification'] == 'Greed']['Closed PnL'].mean()
    
    if fear_pnl > greed_pnl:
        better_sentiment = "Fear"
        diff_pct = ((fear_pnl / abs(greed_pnl)) - 1) * 100 if greed_pnl != 0 else 999
        strategy = "Contrarian"
    else:
        better_sentiment = "Greed"
        diff_pct = ((greed_pnl / abs(fear_pnl)) - 1) * 100 if fear_pnl != 0 else 999
        strategy = "Momentum"
    
    st.markdown(f"""
    <div class="highlight">
    <h3>🎯 Key Insight: {strategy} Strategy Works Best!</h3>
    <p><strong>{better_sentiment}</strong> markets show <strong>{diff_pct:.1f}%</strong> better average PnL</p>
    <p>Fear Avg PnL: <strong>${fear_pnl:.2f}</strong> | Greed Avg PnL: <strong>${greed_pnl:.2f}</strong></p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Win Rate Comparison
        win_rates = df_filtered.groupby('classification')['is_profitable'].mean() * 100
        fig = go.Figure(data=[
            go.Bar(
                x=win_rates.index,
                y=win_rates.values,
                marker_color=['#d32f2f' if x == 'Fear' else '#388e3c' for x in win_rates.index],
                text=win_rates.values.round(1),
                texttemplate='%{text}%',
                textposition='outside'
            )
        ])
        fig.update_layout(
            title="Win Rate: Fear vs Greed",
            yaxis_title="Win Rate (%)",
            height=400
        )
        fig.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50% breakeven")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Average PnL Comparison
        avg_pnl = df_filtered.groupby('classification')['Closed PnL'].mean()
        fig = go.Figure(data=[
            go.Bar(
                x=avg_pnl.index,
                y=avg_pnl.values,
                marker_color=['#d32f2f' if x == 'Fear' else '#388e3c' for x in avg_pnl.index],
                text=avg_pnl.values.round(2),
                texttemplate='$%{text}',
                textposition='outside'
            )
        ])
        fig.update_layout(
            title="Average PnL: Fear vs Greed",
            yaxis_title="Average PnL ($)",
            height=400
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Breakeven")
        st.plotly_chart(fig, use_container_width=True)
    
    # Detailed Sentiment Categories
    st.subheader("📊 Detailed Sentiment Breakdown")
    
    detailed = df_filtered.groupby('sentiment_category').agg({
        'Closed PnL': 'mean',
        'is_profitable': 'mean',
        'roi': 'mean',
        'Account': 'count'
    }).round(2)
    
    detailed.columns = ['Avg PnL', 'Win Rate', 'Avg ROI', 'Trade Count']
    detailed = detailed.sort_values('Avg PnL', ascending=False)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=detailed.index,
        y=detailed['Avg PnL'],
        marker_color=['#c62828', '#e53935', '#fbc02d', '#66bb6a', '#2e7d32'],
        text=detailed['Avg PnL'].round(2),
        texttemplate='$%{text}',
        textposition='outside'
    ))
    fig.update_layout(
        title="Average PnL by Sentiment Category",
        xaxis_title="Sentiment Category",
        yaxis_title="Average PnL ($)",
        height=400
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig, use_container_width=True)
    
    st.dataframe(detailed, use_container_width=True)

# ============================================================
# TAB 3: TRADER INSIGHTS
# ============================================================

with tab3:
    st.header("🏆 Trader Performance Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Top 10 Traders
        st.subheader("🥇 Top 10 Traders by Total PnL")
        top_traders = df_filtered.groupby('Account').agg({
            'Closed PnL': 'sum',
            'is_profitable': 'mean',
            'Account': 'count'
        }).round(2)
        top_traders.columns = ['Total PnL', 'Win Rate', 'Trades']
        top_traders = top_traders.sort_values('Total PnL', ascending=False).head(10)
        top_traders['Win Rate'] = (top_traders['Win Rate'] * 100).round(1).astype(str) + '%'
        st.dataframe(top_traders, use_container_width=True)
    
    with col2:
        # Bottom 10 Traders
        st.subheader("⚠️ Bottom 10 Traders by Total PnL")
        bottom_traders = df_filtered.groupby('Account').agg({
            'Closed PnL': 'sum',
            'is_profitable': 'mean',
            'Account': 'count'
        }).round(2)
        bottom_traders.columns = ['Total PnL', 'Win Rate', 'Trades']
        bottom_traders = bottom_traders.sort_values('Total PnL', ascending=True).head(10)
        bottom_traders['Win Rate'] = (bottom_traders['Win Rate'] * 100).round(1).astype(str) + '%'
        st.dataframe(bottom_traders, use_container_width=True)
    
    # Position Type Analysis
    st.subheader("📊 Long vs Short Performance by Sentiment")
    
    position_perf = df_filtered.groupby(['classification', 'position_type']).agg({
        'Closed PnL': 'mean',
        'is_profitable': 'mean',
        'Account': 'count'
    }).reset_index()
    
    fig = px.bar(
        position_perf,
        x='classification',
        y='Closed PnL',
        color='position_type',
        barmode='group',
        title="Average PnL: Long vs Short by Sentiment",
        color_discrete_sequence=['#1f77b4', '#ff7f0e', '#2ca02c']
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig, use_container_width=True)
    
    # Trader Distribution
    st.subheader("📈 Trader PnL Distribution")
    
    trader_totals = df_filtered.groupby('Account')['Closed PnL'].sum()
    
    fig = go.Figure(data=[go.Histogram(
        x=trader_totals,
        nbinsx=50,
        marker_color='steelblue',
        opacity=0.7
    )])
    fig.update_layout(
        title="Distribution of Total PnL Across Traders",
        xaxis_title="Total PnL ($)",
        yaxis_title="Number of Traders",
        height=400
    )
    fig.add_vline(x=0, line_dash="dash", line_color="red", annotation_text="Breakeven")
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TAB 4: COIN PERFORMANCE
# ============================================================

with tab4:
    st.header("🪙 Cryptocurrency Performance")
    
    # Top coins by volume
    st.subheader("📊 Top Cryptocurrencies by Trading Volume")
    
    coin_stats = df_filtered.groupby('Coin').agg({
        'Closed PnL': ['sum', 'mean'],
        'is_profitable': 'mean',
        'Account': 'count'
    }).round(2)
    coin_stats.columns = ['Total PnL', 'Avg PnL', 'Win Rate', 'Trade Count']
    coin_stats = coin_stats.sort_values('Trade Count', ascending=False).head(10)
    coin_stats['Win Rate'] = (coin_stats['Win Rate'] * 100).round(1).astype(str) + '%'
    
    st.dataframe(coin_stats, use_container_width=True)
    
    # Coin performance by sentiment
    st.subheader("🎯 Best Performing Coins by Sentiment")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 😨 Fear Market")
        fear_coins = df_filtered[df_filtered['classification'] == 'Fear'].groupby('Coin').agg({
            'Closed PnL': 'mean',
            'is_profitable': 'mean',
            'Account': 'count'
        }).round(2)
        fear_coins.columns = ['Avg PnL', 'Win Rate', 'Trades']
        fear_coins = fear_coins[fear_coins['Trades'] >= 10].sort_values('Avg PnL', ascending=False).head(5)
        fear_coins['Win Rate'] = (fear_coins['Win Rate'] * 100).round(1).astype(str) + '%'
        st.dataframe(fear_coins, use_container_width=True)
    
    with col2:
        st.markdown("### 😁 Greed Market")
        greed_coins = df_filtered[df_filtered['classification'] == 'Greed'].groupby('Coin').agg({
            'Closed PnL': 'mean',
            'is_profitable': 'mean',
            'Account': 'count'
        }).round(2)
        greed_coins.columns = ['Avg PnL', 'Win Rate', 'Trades']
        greed_coins = greed_coins[greed_coins['Trades'] >= 10].sort_values('Avg PnL', ascending=False).head(5)
        greed_coins['Win Rate'] = (greed_coins['Win Rate'] * 100).round(1).astype(str) + '%'
        st.dataframe(greed_coins, use_container_width=True)
    
    # Heatmap
    st.subheader("🔥 Coin Performance Heatmap")
    
    top_5_coins = df_filtered['Coin'].value_counts().head(5).index
    heatmap_data = df_filtered[df_filtered['Coin'].isin(top_5_coins)].groupby(
        ['Coin', 'sentiment_category']
    )['Closed PnL'].mean().unstack(fill_value=0)
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=heatmap_data.columns,
        y=heatmap_data.index,
        colorscale='RdYlGn',
        zmid=0,
        text=heatmap_data.values.round(2),
        texttemplate='$%{text}',
        textfont={"size": 10},
        colorbar=dict(title="Avg PnL ($)")
    ))
    fig.update_layout(
        title="Average PnL Heatmap: Top 5 Coins × Sentiment",
        xaxis_title="Sentiment Category",
        yaxis_title="Cryptocurrency",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TAB 5: TIME PATTERNS
# ============================================================

with tab5:
    st.header("⏰ Temporal Trading Patterns")
    
    # Hourly performance
    st.subheader("🕐 Performance by Hour of Day")
    
    hourly = df_filtered.groupby('hour').agg({
        'Closed PnL': 'mean',
        'is_profitable': 'mean',
        'Account': 'count'
    }).round(2)
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig.add_trace(
        go.Bar(x=hourly.index, y=hourly['Closed PnL'], name="Avg PnL", marker_color='steelblue'),
        secondary_y=False
    )
    
    fig.add_trace(
        go.Scatter(x=hourly.index, y=hourly['is_profitable']*100, name="Win Rate", 
                  line=dict(color='red', width=2), mode='lines+markers'),
        secondary_y=True
    )
    
    fig.update_xaxes(title_text="Hour of Day (IST)")
    fig.update_yaxes(title_text="Average PnL ($)", secondary_y=False)
    fig.update_yaxes(title_text="Win Rate (%)", secondary_y=True)
    fig.update_layout(height=400, title="Hourly Trading Performance")
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Day of week performance
    st.subheader("📅 Performance by Day of Week")
    
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    daily = df_filtered.groupby('day_of_week').agg({
        'Closed PnL': 'mean',
        'is_profitable': 'mean',
        'Account': 'count'
    }).reindex(day_order).round(2)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily.index,
        y=daily['Closed PnL'],
        marker_color=['green' if x > 0 else 'red' for x in daily['Closed PnL']],
        text=daily['Closed PnL'].round(2),
        texttemplate='$%{text}',
        textposition='outside'
    ))
    fig.update_layout(
        title="Average PnL by Day of Week",
        xaxis_title="Day",
        yaxis_title="Average PnL ($)",
        height=400
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig, use_container_width=True)
    
    # Best/Worst Times
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### ✅ Best Trading Hours")
        best_hours = hourly.nlargest(5, 'Closed PnL')[['Closed PnL', 'is_profitable', 'Account']]
        best_hours.columns = ['Avg PnL', 'Win Rate', 'Trades']
        best_hours['Win Rate'] = (best_hours['Win Rate'] * 100).round(1).astype(str) + '%'
        st.dataframe(best_hours, use_container_width=True)
    
    with col2:
        st.markdown("### ⚠️ Worst Trading Hours")
        worst_hours = hourly.nsmallest(5, 'Closed PnL')[['Closed PnL', 'is_profitable', 'Account']]
        worst_hours.columns = ['Avg PnL', 'Win Rate', 'Trades']
        worst_hours['Win Rate'] = (worst_hours['Win Rate'] * 100).round(1).astype(str) + '%'
        st.dataframe(worst_hours, use_container_width=True)

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p><strong>Bitcoin Trader Sentiment Analysis Dashboard</strong></p>
    <p>Created by <strong>Navneet Shukla</strong> for PrimeTrade.ai</p>
    <p>Data Science Assessment | November 2025</p>
    <p>📧 <a href="mailto:your.email@example.com">Contact</a> | 
       🔗 <a href="https://github.com/yourusername">GitHub</a> | 
       💼 <a href="https://linkedin.com/in/yourprofile">LinkedIn</a></p>
</div>
""", unsafe_allow_html=True)