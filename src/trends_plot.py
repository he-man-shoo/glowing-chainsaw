import plotly.graph_objects as go


def trends_plot_fig(df):

    fig = go.Figure()

    fig.add_trace(go.Scatter(y = (df['Original (CNY/mt)']).to_list(), x = df['Date'].to_list(), \
                            mode = 'lines', name = 'Original (USD/mt equivalent)'))
    # fig.add_trace(go.Scatter(y = df['VAT Included (USD/mt)'].to_list(), x = df['Date'].to_list(), \
    #                         mode = 'lines', name = 'VAT Included (USD/mt)'))
    # fig.add_trace(go.Scatter(y = df['VAT Excluded (USD/mt)'].to_list(), x = df['Date'].to_list(), \
    #                         mode = 'lines', name = 'VAT Excluded (USD/mt)'))

    fig.update_layout(title = "Li Carbonate Price Trends", yaxis_title ="CNY/mt")

    return fig