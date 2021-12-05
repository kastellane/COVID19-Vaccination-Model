import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from model import sample_param_combinations, run_model_sampling


def get_country_data():

    df = pd.read_csv(
        "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations.csv"
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["location", "date"])

    columns_to_keep = [
        "location",
        "date",
        "people_vaccinated_per_hundred",
        "daily_vaccinations_per_million",
    ]

    df = df.loc[:, columns_to_keep]

    avail_countries = df["location"].unique()
    country_data = pd.pivot_table(
        df,
        columns="location",
        values=[
            "people_vaccinated_per_hundred",
            "daily_vaccinations_per_million",
        ],
        index="date",
    )

    return avail_countries, country_data


colors = px.colors.qualitative.Safe

to_plot = [
    "people_vaccinated_per_hundred",
    "daily_vaccinations_per_million",
    "cum_number_vac_received_per_hundred",
    "vaccines_in_stock_per_hundred",
]


def add_line(
    fig, x, y, color, name=None, row=1, col=1, fill="none", width=2, annotation=False
):

    # plot line

    data = dict(
        x=x,
        y=y,
        mode="lines",
        fill=fill,
        line_shape="spline",
        showlegend=False,
        line=dict(color=color, width=width),
    )

    if name is not None:
        data["legendgroup"] = name
        data["name"] = name

    fig.add_trace(
        go.Scatter(data),
        row=row,
        col=col,
    )

    # write annotation
    if annotation:

        fig.add_annotation(
            xref="paper",
            x=x[-1],
            y=y[-1],
            xanchor="left",
            yanchor="middle",
            text=name,
            font=dict(family="Arial", size=14, color=color),
            showarrow=False,
            row=row,
            col=col,
        )

    return fig


def plot_model_results(model_results, CI):

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "People vaccinated per hundred",
            "Daily vaccinations per million",
            "Vaccines received per hundred",
            "Vaccines in stock per hundred",
        ),
        horizontal_spacing=0.08,
        vertical_spacing=0.15,
    )

    for n, k in enumerate(to_plot):

        i, j = np.unravel_index(n, [2, 2])
        i += 1
        j += 1

        # ---- plot model results ----
        # the first automatic call will have no stored model_results and it will be None

        if model_results is not None:
            df = model_results[k]
            fig = add_line(
                fig,
                df["dates"],
                df["mean"],
                "royalblue",
                "Model",
                i,
                j,
                annotation=True,
            )
            fig = add_line(
                fig,
                df["dates"],
                df["upper"],
                colors[0],
                f"Model CI={CI}%",
                i,
                j,
                width=0,
                annotation=False,
            )
            fig = add_line(
                fig,
                df["dates"],
                df["lower"],
                colors[0],
                f"Model CI={CI}%",
                i,
                j,
                width=0,
                fill="tonexty",
                annotation=False,
            )

    # fig.update_yaxes(range=[0, 100], row=1, col=1)
    fig.update_layout(margin=dict(l=0, r=0, b=0, t=50))  # height=400, width=1100)

    return fig


def plot_country_data(fig, selected_countries, country_data, initialized=False):

    for n, k in enumerate(to_plot):

        i, j = np.unravel_index(n, [2, 2])
        i += 1
        j += 1

        # ----- add curves with data from the selected countries ----
        if k in country_data.columns:
            df = country_data[k]
            for ncolor, country in enumerate(selected_countries):
                g = df[country].dropna()
                fig = add_line(
                    fig,
                    g.index,
                    g,
                    colors[ncolor + 1],
                    country,
                    i,
                    j,
                    width=1,
                    annotation=True,
                )
        else:
            # Some of the results that we obtain from the model do not have equivalent real world data.
            # This causes some plots not to show up initially, until the model has ben run at least once.
            # If model results are not yet available, we place a 'no data' annotation in those plots.
            # That will make Plotly draw the axes so the user will be aware of them from the begining.
            if initialized:

                fig = add_line(
                    fig,
                    [0],
                    [0],
                    colors[0],
                    "No data to show",
                    i,
                    j,
                    width=1,
                    annotation=True,
                )

    return


def run_model(
    # populatio parameters
    p_pro_bounds,
    p_anti_bounds,
    pressure_bounds,
    # vaccinations parameters
    tau_bounds,
    nv_0_bounds,
    nv_max_bounds,
    # samping
    CI,
    n_rep,
    N,
    date_range,
    max_running_time=None,
):

    # default output messages
    msg_agnostics_pct = "Agnosticts: "
    msg_error = ""

    # if (nv_0_bounds[0]/100)*N < 1:
    # msg_error = "WARNING: The initial stock of vaccines implies {0:.2f} vaccines initially available. Please, increase the lower bound for the initial stock or the population size so that 1 or more vaccines are available.".format((nv_0_bounds[0]/100)*N)
    # return fig, None, msg_agnostics_pct, msg_error, model_results

    # some sliders use values 0-100
    params_combinations, p_soft_no_values = sample_param_combinations(
        np.array(p_pro_bounds) / 100,
        np.array(p_anti_bounds) / 100,
        np.array(pressure_bounds),
        np.array(tau_bounds),
        np.array(nv_0_bounds) / 100,
        np.array(nv_max_bounds) / 100,
        n_rep,
    )

    if params_combinations is not None:
        # evaluate the agnostics population from the pro and anti vaccines samples
        p_soft_no_values = 100 * np.array(p_soft_no_values)
        a = max(np.mean(p_soft_no_values) - np.std(p_soft_no_values), 0)
        b = np.mean(p_soft_no_values) + np.std(p_soft_no_values)
        a_str = "{0:.0f}".format(a)
        b_str = "{0:.0f}".format(b)
        # if the uncertainty interval is smaller than 1%, report one value instead of the interval
        if abs(a - b) < 1:
            msg_agnostics_pct += a_str + "%"
        else:
            msg_agnostics_pct += a_str + " - " + b_str + "%"
    else:
        msg_error = "ERROR: The pertentages of pro- and anti-vaccines are simultaneously too high. Please reduce them."
        return None, msg_error, msg_agnostics_pct

    model_results = run_model_sampling(
        params_combinations,
        date_range["start_date"],
        date_range["end_date"],
        CI / 100,
        N,
        max_running_time,
    )

    if max_running_time is not None:
        number_finished_samples = model_results["number_finished_samples"]
        if number_finished_samples < len(params_combinations):
            msg_error = f"ERROR: Maximum computation time of {max_running_time}s exceeded. Only {number_finished_samples} of the desired {len(params_combinations)} Monte Carlo runs were performed."

    return model_results, msg_error, msg_agnostics_pct


def main():

    # populatio parameters
    p_pro_bounds = [30, 40]
    p_anti_bounds = [30, 40]
    pressure_bounds = [0.02, 0.02]
    # vaccinations parameters
    tau_bounds = [4, 4]
    nv_0_bounds = [0.2, 0.2]
    nv_max_bounds = [10, 10]
    # samping
    n_rep = 100
    N = 50000
    start_date = "2020-12-30"
    end_date = "2021-12-1"
    CI = 0.95

    date_range = dict(start_date=start_date, end_date=end_date)

    model_results, msg_error, msg_agnostics_pct = run_model(
        # populatio parameters
        p_pro_bounds,
        p_anti_bounds,
        pressure_bounds,
        # vaccinations parameters
        tau_bounds,
        nv_0_bounds,
        nv_max_bounds,
        # samping
        CI,
        n_rep,
        N,
        date_range,
    )

    fig = plot_model_results(model_results, CI)

    # plot_country_data(fig, selected_countries, country_data)

    fig.show(renderer="browser")


if __name__ == "__main__":
    main()