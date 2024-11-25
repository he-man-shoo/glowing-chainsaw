import plotly.graph_objects as go


def trends_plot_fig(df):

    fig = go.Figure()

    fig.add_trace(go.Scatter(y = (df['Original (CNY/mt)']).to_list(), x = df['Date'].to_list(), \
                            mode = 'lines', name = 'Original (USD/mt equivalent)'))

    fig.update_layout(title = "Li Carbonate Price Trends", yaxis_title ="CNY/mt")

    fig.update_layout(
            plot_bgcolor='rgb(255, 255, 255)', # Light grey background 
            paper_bgcolor='rgb(255, 255, 255)', # Very light grey paper background
            
            xaxis=dict(showgrid=True, # Show gridlines 
                       gridcolor='rgb(200, 200, 200)', # Gridline color 
                       gridwidth=1, # Gridline width
                       zeroline=False, # Remove zero line
                       ),
                       
    )

    return fig