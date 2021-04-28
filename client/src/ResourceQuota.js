import React from 'react';
import { TextField, Tooltip } from '@material-ui/core';

class QuotaParameter extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            name: this.props.parameter["name"],
            units: (this.props.parameter["units"] === '' ? '' : '(' + this.props.parameter["units"] + ')'),
            regex: new RegExp(this.props.parameter["regex"]),
            regex_description: this.props.parameter["regex_description"],

            value: this.props.parameter[""]
        };

        this.validate = this.validate.bind(this)
    };

    validate(event) {

        // test input with regex
        if (event.target.value === '' || this.state.regex.test(event.target.value)) {

            // set field text
            this.setState({
                value: event.target.value
            })

            // edit quota object
            this.props.edit(this.props.parameter_name, event.target.value)
        }

    }

    render() {
        return (
            <TextField
                id={this.props.parameter_name}
                name={this.props.parameter_name}
                label={this.state.name + " " + this.state.units}
                helperText={this.state.regex_description}
                value={this.state.value}
                onChange={event => this.validate(event)}
                fullWidth
            />
        )
    }

}

class ResourceQuota extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            quota: {}
        };

        this.edit = this.edit.bind(this)
    };

    edit(name, value) {

        let quota = this.state.quota

        // if empty - remove from quota
        if (value === '') {
            delete quota[name]
        } else {
            quota[name] = value
        }

        this.setState({
            quota: quota
        })

        this.props.edit(this.props.name, quota)
    }

    render() {

        return (
            <div>
                {Object.keys(this.props.fields).map(parameter_name =>
                    <div style={{ marginTop: "10px" }}>
                        <QuotaParameter parameter_name={parameter_name} parameter={this.props.fields[parameter_name]} edit={this.edit}></QuotaParameter>
                    </div>
                )}
            </div>
        )

    }

}

export default ResourceQuota;